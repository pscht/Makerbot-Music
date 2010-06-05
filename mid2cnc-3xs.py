# mid2cnc.py, a MIDI to CNC g-code converter
# by T. R. Gipson <drmn4ea at google mail>
# http://tim.cexx.org/?p=633
# Released under the GNU General Public License

# Includes midiparser.py module by Sean D. Spencer
# http://seandon4.tripod.com/
# This module is public domain.
#
# Modified for use with the MakerBot 
# by H. Grote <hg at pscht dot com>
# 
# More info on:
# http://groups.google.com/group/makerbotmusic


import sys
import midiparser
import math

imported_channels=[0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15]  # List of MIDI channels (instruments) to import.
                                                     
xposdist = 0
xnegdist = 0

yposdist = 0
ynegdist = 0

zposdist = 0
znegdist = 0

# Makerbots NEMA 17 has 200 SPR which is 1.8 degrees per rotation
xy_ppi = 600
z_ppi = 600 # 18000 set z-axis to super pursuit mode (testing only)

#machine_safety = 0.2
#machine_limit_x = 3.93 # 
#machine_limit_y = 3.93 # 
#machine_limit_z = 1 # 

suppress_comments = 0 # Set to 1 if your machine controller does not handle ( comments )


tempo=None # should be set by your MIDI...



def main(argv):

    print "DISCLAIMER: THIS PROGRAM COMES WITH NO WARRANTY\nPLEASE KEEP AN EYE ON YOUR MAKERBOT AS THE GENERATED GCODE \nMAY BRING YOUR BUILD PLATFORM OFF LIMITS!\n "   
    x=0.0
    y=0.0
    z=0.0

    x_dir=1.0;
    y_dir=1.0;
    z_dir=1.0;

    if len(sys.argv) <= 2:
        print "Usage: ./python mid2cnc-3xs.py <inputfile>.mid <outputfile>.gcode\n" 
        sys.exit(1) 
    else:
        midifile = argv[1]
        outfile = argv[2]

    FILE = open(outfile,"w")
    midi = midiparser.File(midifile)
    
    print midi.file, midi.format, midi.num_tracks, midi.division

    noteEventList=[]

    for track in midi.tracks:
        for event in track.events:
            if event.type == midiparser.meta.SetTempo:
                tempo=event.detail.tempo
                #tempo = "60"
                print "Tempo change: " + str(event.detail.tempo)
            if ((event.type == midiparser.voice.NoteOn) and (event.channel in imported_channels)): # filter undesired instruments
                #print event.absolute, 
                #print event.detail.note_no, event.detail.velocity
                # NB: looks like some use "note on (vel 0)" as equivalent to note off, so check for vel=0 here and treat it as a note-off.
                if event.detail.velocity > 0:
                    noteEventList.append([event.absolute, 1, event.detail.note_no, event.detail.velocity])
                else:
                    noteEventList.append([event.absolute, 0, event.detail.note_no, event.detail.velocity])
            if (event.type == midiparser.voice.NoteOff) and (event.channel in imported_channels):
                #print event.absolute, 
                #print event.detail.note_no, event.detail.velocity
                noteEventList.append([event.absolute, 0, event.detail.note_no, event.detail.velocity])
            if event.type == midiparser.meta.TrackName: 
                print event.detail.text.strip()
            if event.type == midiparser.meta.CuePoint: 
                print event.detail.text.strip()
            if event.type == midiparser.meta.Lyric: 
                print event.detail.text.strip()
                #if event.type == midiparser.meta.KeySignature: 
                # ...

    # We now have entire file's notes with abs time from all channels
    # We don't care which channel/voice is which, but we do care about having all the notes in order
    # so sort event list by abstime to dechannelify

    noteEventList.sort()
    #print noteEventList

    print len(noteEventList)
    last_time=-0
    active_notes={} # make this a dict so we can add and remove notes by name

    # Start the file...
    # It would be nice to add some metadata here, such as who/what generated the output, what the input file was,
    # and important playback parameters (such as steps/in assumed and machine envelope).
    # Unfortunately G-code comments are not 100% standardized...

    if suppress_comments == 0:
        FILE.write ("( Input file was " + midifile + " )\n")

# Didn't find it very useful the way it was implemented - changed the working envelope calculation to a safer variant
#        FILE.write ("( Machine envelope: )\n")
#        FILE.write ("( x = " + str(machine_limit_x) + " )\n")
#        FILE.write ("( y = " + str(machine_limit_y) + " )\n")
#        FILE.write ("( z = " + str(machine_limit_z) + " )\n")


    
    FILE.write ("G21\n")            # Set units to metric (metric ftw!)
    FILE.write("G00 X0 Y0 Z0\n")    # Home


    # General description of what follows: going through the chronologically-sorted list of note events, (in big outer loop) adding
    # or removing them from a running list of active notes (active_notes{}). Generally all the notes of a chord will turn on at the
    # same time, so nothing further needs to be done. If the delta time changes since the last note, though, we know how long the
    # last chord should play for, so dump out the running list as a linear move and continue collecting note events until the next
    # delta change...

    for note in noteEventList:
        #print note # [event.absolute, 0, event.detail.note_no, event.detail.velocity]
        if last_time < note[0]:
            # New time, so dump out current noteset for the time between last_time and the present, BEFORE processing new updates.
            # Whatever changes at this time (delta=0) will be handled when the next new time (nonzero delta) appears.
            
            freq_xyz=[0,0,0]
            feed_xyz=[0,0,0]
            feed_z=0
            adapted_feed_xyz=[0,0,0]
            adapted_distance_xyz=[0,0,0]
            distance_xyz=[0,0,0]
            distance_z=0

            for i in range(0, min(len(active_notes.values()), 3)): # number of axes for which to build notes
                # If there are more notes than axes, use the highest of the available notes, since they seem to sound the best
                # (lowest frequencies just tend to sound like growling and not musical at all)
                nownote=sorted(active_notes.values(), reverse=True)[i]
                freq_xyz[i] = pow(2.0, (nownote-69)/12.0)*440.0 # convert note numbers to frequency for each axis in Hz
                feed_xyz[i] = (freq_xyz[i] * 60.0 / xy_ppi) *25.4   # feedrate in IPM for each axis individually
                feed_z = (freq_xyz[2] * 60.0 / z_ppi)

#               Debug info: current song tempo
#               print("TEMPO: %.2F\n" % (tempo))

                distance_xyz[i] =  feed_xyz[i] * ((((note[0]-last_time)+0.0)/(midi.division+0.0)) * ((tempo)/60000000.0))*25.4
                distance_z =  feed_z * ((((note[0]-last_time)+0.0)/(midi.division+0.0)) * ((tempo)/60000000.0))

                # Also- what on earth were they smoking when they made precision of a math operation's output dependent on its undeclared-types value at any given moment?
                # (adding 0.0 to numbers above forces operations involving them to be computed with floating-point precision in case the number they contain happens to be an integer once in a while)

            print "Chord: [%.3f, %.3f, %.3f] for %d deltas" % (freq_xyz[0], freq_xyz[1], freq_xyz[2], (note[0] - last_time))

            # So, we now know the frequencies assigned to each axis and how long to play them, thus the distance.
            # So write it out as a linear move...

            # Feedrate from frequency: f*60/machine_ppi
            # Distance (move length): feedrate/60 (seconds); feedrate/60000 (ms)

            # And for the combined (multi-axis) feedrate... arbitrarily select one note as the reference, and the ratio of the
            # final (unknown) feedrate to the reference feedrate should equal the ratio of the 3D vector length (known) to the
            # reference length (known). That sounds too easy.

            # First, an ugly bit of logic to reverse directions if approaching the machine's limits



#            Debug information - spams the console with distance information if activated
#            print("x-distance is: %.10F while x-limit is: %.10F\n" % (x, machine_limit_x-machine_safety))
#            print("sum of pos. x-distance is: %.10F, while sum of neg. x-distance is: %.10F\n" % (xposdist, xnegdist))
#            print("difference is: %.10F\n" % (xposdist+xnegdist))

            x = ((distance_xyz[0] * x_dir))/25.4
            if x >= 0: 
                global xposdist
                xposdist = xposdist + x
            else:
                global xnegdist
                xnegdist = xnegdist + x

            if (xposdist+xnegdist) > 10:
                x_dir = -1
#                print("had to turn directions...\n")
            if (xposdist+xnegdist) <= 10:
                x_dir = 1

            y = ((distance_xyz[1] * y_dir))/25.4
            if y >= 0: 
                global yposdist
                yposdist = yposdist + y
            else:
                global ynegdist
                ynegdist = ynegdist + y
            if (yposdist+ynegdist) > 20:
                y_dir = -1
            if (yposdist+ynegdist) <= 20:
                y_dir = 1
                
            z = ((distance_z * z_dir))
            if z >= 0: 
                global zposdist
                zposdist = zposdist + z
            else:
                global znegdist
                znegdist = znegdist + z
            if (zposdist+znegdist) > 20.0:
                z_dir = -1
            if (zposdist+znegdist) <= 20.0:
                z_dir = 1
                
            adapted_distance_xyz=[distance_xyz[0], distance_xyz[1], distance_z]   
            adapted_feed_xyz=[(feed_xyz[0]),(feed_xyz[1]),feed_z]
#            print("adapted feedrate is: %.10F / %.10F / %.10F\n" % (adapted_feed_xyz[0],adapted_feed_xyz[1],adapted_feed_xyz[2]))
            

            if adapted_distance_xyz[0] > 0: # handle 'rests' in addition to notes. How standard is this pause gcode, anyway?
                vector_length = math.sqrt(adapted_distance_xyz[0]**2 + adapted_distance_xyz[1]**2 + adapted_distance_xyz[2]**2)
                combined_feedrate = (vector_length / adapted_distance_xyz[0]) * adapted_feed_xyz[0]
                FILE.write("G01 X%.10f Y%.10f Z%.10f F%.10f\n" % (x, y, z, combined_feedrate))
            else:
                temp = int((((note[0]-last_time)+0.0)/(midi.division+0.0)) * (tempo/1000.0))
                FILE.write("G04 P%0.4f\n" % (temp/1000.0))

            # finally, set this absolute time as the new starting time
            last_time = note[0]

        if note[1]==1: # Note on
            if active_notes.has_key(note[2]):
                print "Warning: tried to turn on note already on!"
            else:
                active_notes[note[2]]=note[2] # key and value are the same, but we don't really care.
        elif note[1]==0: # Note off
            if(active_notes.has_key(note[2])):
                active_notes.pop(note[2])
            else:
                print "Warning: tried to turn off note that wasn't on!"


#    FILE.write("G01 X0 Y0 Z0 F1000\n")
    
if __name__ == "__main__":
    main(sys.argv)


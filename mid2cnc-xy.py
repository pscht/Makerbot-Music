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


midifile = "Tetris_MusicA2.mid"
outfile = "Tetris.gcode"

# 2,3,4,5,6,7,8,9,10,11,12,13,14,15
imported_channels=[0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15]  # List of MIDI channels (instruments) to import.
                                                     
xposdist = 0
xnegdist = 0

yposdist = 0
ynegdist = 0

zposdist = 0
znegdist = 0

machine_ppi = 634.74209172
# machine_ppi = 507.999448

suppress_comments = 0 # Set to 1 if your machine controller does not handle ( comments )


tempo=None # should be set by your MIDI...



def main(argv):

    x=0.0
    y=0.0
    z=0.0

    x_dir=1.0;
    y_dir=1.0;
    z_dir=1.0;

    FILE = open(outfile,"w")

    #midi = midiparser.File(argv[1])
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
        FILE.write ("G21\n")            # Set units to metric
        FILE.write("G00 X0 Y0 Z0\n")    # Home


    for note in noteEventList:
        if last_time < note[0]:
        
            freq_xyz=[0,0,0]
            feed_xyz=[0,0,0]
            distance_xyz=[0,0,0]

            for i in range(0, min(len(active_notes.values()), 2)): 
                nownote=sorted(active_notes.values(), reverse=True)[i]
                freq_xyz[i] = pow(2.0, (nownote-69)/12.0)*440.0 
                feed_xyz[i] = (freq_xyz[i] * 60.0 / machine_ppi)*25.4 
                print("TEMPO: %.2F\n" % (tempo))
                distance_xyz[i] =  feed_xyz[i] * (((((note[0]-last_time)+0.0)/(midi.division+0.0)) * ((tempo)/60000000.0)) * 25.4)  
            
            print "Chord: [%.3f, %.3f, %.3f] for %d deltas" % (freq_xyz[0], freq_xyz[0], freq_xyz[0], (note[0] - last_time))

            x = (x + (distance_xyz[0] * x_dir))/25.4
            if x >= 0: 
            	global xposdist
            	xposdist = xposdist + x
            else:
            	global xnegdist
            	xnegdist = xnegdist + x
 #           print("x-distance is: %.10F while x-limit is: %.10F\n" % (x, machine_limit_x-machine_safety))
 #           print("sum of pos. x-distance is: %.10F, while sum of neg. x-distance is: %.10F\n" % (xposdist, xnegdist))
           
            print("difference is: %.10F\n" % (xposdist+xnegdist))
            if (xposdist+xnegdist) > 30.0:
                x_dir = -1
                print("had to turn directions...\n")
            if (xposdist+xnegdist) <= 30.0:
                x_dir = 1

            y = (y + (distance_xyz[1] * y_dir))/25.4
            if y >= 0: 
            	global yposdist
            	yposdist = yposdist + y
            else:
            	global ynegdist
            	ynegdist = ynegdist + y
            if (yposdist+ynegdist) > 20.0:
                y_dir = -1
            if (yposdist+ynegdist) <= 20.0:
                y_dir = 1
                
            z = (z + (distance_xyz[2] * z_dir))/25.4
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
                
            if distance_xyz[0] > 0: # handle 'rests' in addition to notes. How standard is this pause gcode, anyway?
                vector_length = math.sqrt(distance_xyz[0]**2 + distance_xyz[1]**2 + distance_xyz[2]**2)
                combined_feedrate = (vector_length / distance_xyz[0]) * feed_xyz[0]
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

    
if __name__ == "__main__":
    main(sys.argv)

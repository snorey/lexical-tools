# -*- coding: utf-8 -*-

import os, re
import datetime, time
import pie

def hsk2voc(file):
	voc=pie.Vocabulary(language="Mandarin")
	for line in file:
		pieces=line.split(",")
		word=pie.Word()
# This is for "HSK Level,Word,Pronunciation,Definition," format
		try: level=int(pieces[0])
		except ValueError: continue
		word.mainform=pieces[1].decode("utf-8","ignore")
		word.rom=pieces[2].decode("utf-8","ignore")
		word.glossed=pieces[3].decode("utf-8","ignore")
		glosses=word.glossed.split(";")
		glosses=[x.strip() for x in glosses]
		word.glosses=glosses
		if len(glosses) > 1 and glosses[0].startswith("("):
			word.gloss=glosses[1]
		else:
			word.gloss=glosses[0]
		word.tally=1000/level
		word.phonetic=rom2bopo(word.rom)
		word.language="Mandarin"
		voc.add(word)
	return voc
		

def rom2bopo(rom=""):
	return rom
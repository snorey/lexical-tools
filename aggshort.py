#!/usr/bin/python
# -*- coding: utf-8  -*-

import os, re

scriptdir="C:\Code" # Where the code and control files live

def titlegrabber(lang="English"):
	import xmlreader
	totalfile=open(scriptdir+"\\all_titles.txt","w")
	writefile=open(scriptdir+"\\en_titles.txt","w")
	English=set()
	all=set()
	if "wikt.xml" not in os.listdir(scriptdir):
		dump=xmlreader.XmlDump(scriptdir+"\wikt.bz2")
	else:
		dump=xmlreader.XmlDump(scriptdir+"\wikt.xml")
	for d in dump.parse():
		all.add(d.title)
		if ":" in d.title: continue
		elif "=="+lang+"==" not in d.text: continue
		else: English.add(d.title)
		try: print d.title, len(English)
		except: pass
	for e in English:
		writefile.write(e.encode("utf-8")+"\r\n")
	for a in all:
		totalfile.write(a.encode("utf-8")+"\r\n")
	writefile.close()
	totalfile.close()
	return English

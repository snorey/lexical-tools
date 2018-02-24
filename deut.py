# -*- coding: utf-8 -*-

import os, re
import datetime, time
import urllib2

def lemmatize(word,freqlist):
	morefreq=set(freqlist[:freqlist.index(word)])
	morefreq.remove(word)
	lessfreq=set(freqlist[freqlist.index(word):])
	if len(word) < 4:
		return word
	if word==word.title(): # noun
		if not word.endswith("e") and not word.endswith("n") and not word.endswith("er"): 
			return word
		elif word.endswith("e"):
			if word[:-1] in morefreq:
				return word[:-1]
		elif word.endswith("n"):
			if word.endswith("en"):
				if word[:-2] in morefreq:
					return word[:-2]
	elif word==word.lower(): # adjective or verb or whatever
		if word.startswith("ge") and word.endswith("t"):
			if word[:-1]+"n" in wordlist:
				return word[:-1]+"n"
			elif word[2:-1]+"n" in wordlist:
				return word[2:-1]+"n"
		elif word.endswith("n"):
			if word.endswith("eten") and len(word) > 6:
				if word[:-3]+"n" in morefreq:
					return word[:-3]+"n"
			elif word.endswith("en"):
				if word[:-2] in morefreq:
					return word[:-2]
				elif deumlaut(word[:-2]) in morefreq:
					return deumlaut(word[:-2])
		elif word.endswith("e"):
			if word.endswith("ete") and len(word) > 5:
				if word[:-2]+"n" in morefreq:
					pass
			if word[:-3]+"n" in morefreq:
				return word[:-3]+"n"
			if word[:-1] in wordlist:
				return word[:-1]
			elif deumlaut(word[:-1]) in morefreq:
				return deumlaut(word[:-1])
		elif word.endswith("t"):
			if word.endswith("st"):
				if word[:-2]+"n" in wordlist:
					return word[:-2]+"n"
				elif word[:-2]+"en" in wordlist:
					return word[:-2]+"en"
			elif word[:-1]+"n" in wordlist:
				return word[:-1]+"n"
		elif word.endswith("s"): # neuter adj?
			if word.endswith("es") and word[:-2] in wordlist:
				return word[:-2]
			elif word[:-1] in wordlist:
				return word[:-1]
		elif word.endswith("er"):
			if word[:-2] in wordlist:
				return word[:-2]
# still here?
	return word
	
def deumlaut(word):
	word=word.replace("ä","a")
	word=word.replace("ö","o")
	word=word.replace("ü","u")
	return word
	
def stern(date=datetime.date.today()):
	datestring=date.isoformat().replace("-","/")
	directory="D:\\Corp\\Stern\\"+datestring.replace("/","")
	try:
		os.mkdir(directory)
	except: 
		pass
	already=set(os.listdir(directory))
	starturl="http://wefind.stern.de/archiv/alle/"+datestring
	startpage=urllib2.urlopen(starturl).read()
	articles=set()
	articles|=stern_process_page(startpage)
	morecounter=1
	theresmore=1
	while theresmore:
		moreurl=starturl+"/" 
		moreurl+=str(morecounter) 
		print moreurl
		try: 
			morepage=urllib2.urlopen(moreurl,timeout=10).read()
		except:
			print "Error..."
			time.sleep(5)
			continue
		newarticles=stern_process_page(morepage)
		articles|=newarticles
		theresmore=len(newarticles)
		morecounter+=1
		time.sleep(1)
	articles=list(articles)
	print len(articles)
	for a in articles:
		url=a
		print url, articles.index(a)
		filename=a.split("/")[-1][:100]
		if filename in already: continue
		try:
			articlepage=urllib2.urlopen(url,timeout=10).read()
			time.sleep(1)
		except:
			print "Error!"
			time.sleep(5)
			continue
		writefile=open(os.path.join(directory,filename),"w")
		with writefile:
			writefile.write("<url>%s</url>" % url)
			writefile.write(articlepage)

def stern_process_page(page=""):
	matcher='\<a class\=\"h2\" href\=\"(http\:.*?)\"'
	articles=set(re.findall(matcher,page))
	print str(len(articles))
	return articles

	
def suedd():
	urlpattern="http://suche.sueddeutsche.de/query/%%23/nav/%%C2%%A7documenttype%%3AArtikel/sort/-docdatetime/page/%s"
	directory="C:\\Corp\\Sueddeutsche"
	counter=1
	dirs=os.listdir(directory)
	while counter < 14000:
		url=urlpattern % str(counter)
		print url
		page=urllib2.urlopen(url).read()
		splitter='" class="entry-title"'
		pieces=page.split(splitter)
		print len(pieces)
		for piece in pieces[:-1]:
			pieceurl=piece.split('"')[-1]
			if not pieceurl.startswith("http://www.sueddeutsche"):
				continue
			if "/thema/" in pieceurl:
				continue
			print pieceurl
			desc=pieces[pieces.index(piece)+1].split('<p class="entry-summary">')[1].strip()
			date=desc.split(" ")[0].split(".")
			if len(date) != 3: 
				print "bad date: "+date
				continue
			dom=date[0]
			month=date[1]
			year=date[2]
			datestring="%s-%s-%s" % (year,month,dom)
			datedir=os.path.join(directory,datestring)
			if datestring not in dirs:
				os.mkdir(datedir)
				dirs.append(datestring)
			thispage=urllib2.urlopen(pieceurl).read()
			file=open(os.path.join(datedir,pieceurl.split("/")[-1])+".html","w")
			with file:
				file.write(thispage)
		counter+=1
		
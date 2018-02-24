import datetime
import os 
import re
from string import punctuation as punx
import urllib
import xml.etree.cElementTree as ET

import Stemmer
import pie

pluspunx=[unichr(x).encode("utf-8") for x in [171,187]] # double angle brackets

class WiktiParser:
	def __init__(self):
		self.forms = {}
		self.words = {}
		self.entries = set()
		self.language="Russian"
		self.langcode="ru"
		self.learned=set()
		self.stemmer=Stemmer.Stemmer('russian')

	def process(self,filepath="C:\\Code\\enwikt.xml"): 
		file=open(filepath,"r")
		thispage = ""
		reading = False
		self.inflectiontables=set()
		for line in file:
			if "<page>" in line:
				reading = True
			if reading is True:
				thispage += line+"\n"
			if "</page>" in line:
				if "==%s" % self.language in thispage or "== %s"  % self.language in thispage:
					thing = ET.XML(thispage)
					reading = False
					thispage = ""
					title = thing.findtext("title")
					if ":" in title:
						continue
					entry = thing.find("revision").findtext("text")
					if title not in self.words.keys():
						self.words[title] = self.process_entry(entry,title)
					else: # main entry gets priority
						self.words[title] = self.process_entry(entry,title) + self.words[title]
				if ("==English" in thispage or "== English" in thispage) and ("===Translations" in thispage or "=== Translations" in thispage):
					thing = ET.XML(thispage)
					reading = False
					thispage = ""
					title = thing.findtext("title")
					if ":" in title:
						continue
					entry = thing.find("revision").findtext("text")
					translations = re.findall("\{\{t[\+\-]*\|%s\|(.+?)[\|\}]"  % self.langcode,entry)
					for t in translations:
						if t.startswith("[["):
							t=t.split("[[")[1].split("]]")[0]
						if t in self.words.keys():
							self.words[t].append(title)
						else:
							self.words[t] = [title]
				thispage = ""
				reading = False
				continue

	def debug(self,path="C:\\Code\\ru-debug.txt"):
		words_paired=[x+"\t"+str(self.wordsintext.count(x))+"\t"+self.stemsintext[self.wordsintext.index(x)]+"\t"+str(self.stemsintext.count(self.stemsintext[self.wordsintext.index(x)])) for x in set(self.wordsintext)]
		words_paired=[x.encode("utf-8","ignore") for x in words_paired]
		outfile=open(path,"w")
		with outfile:
			outfile.write("Words in text\nType\tFrequency\tStem\tFrequency\n\n")
			outfile.write("\n".join(words_paired))

	def session(self,target=0.9,readingpath="C:\\Code\\kara_1.txt"):
		if not self.words:
			print "No vocabulary loaded. Loading."
			self.process()
		text=open(readingpath).read()
		for p in punx:
			text=text.replace(p," ")
		words=[x.decode("utf-8","ignore") for x in text.split()]
		self.wordsintext=words
		print len(words),len(set(words))
		stems=self.stemmer.stemWords(words)
		print len(stems),len(set(stems))
		self.stemsintext=stems
		freqlist=[x.split(" ")[2].strip().decode("utf-8") for x in open("C:\\Code\\lemma.num").read().split("\n") if x.strip()]
		self.freqlist=freqlist
		known=set()
		print "Spooling up."
		self.stemmedwords=self.stemmer.stemWords(self.words.keys())
		self.stems2words=dict(zip(self.stemmedwords,self.words.keys()))
		self.words2stems=dict(zip(self.words.keys(),self.stemmedwords))
		self.get_forms()
		print "Let's go."
		#1. rank words by local frequency
		freqs={}
		lemmata=dict(zip(list(set(words)),list(set(words))))
		for type in set(words):
			lemma=""
			if not type.islower():
				lemmata[type]=lemma
				continue
			elif type in freqlist:
				lemma=type
			elif type in self.formdic.keys():
				lemma=self.formdic[type][0]
			elif self.stemmer.stemWord(type) in self.stems2words.keys():
				lemma=self.stems2words[self.stemmer.stemWord(type)]
			else:
				lemma=type
			if lemma:
				lemmata[type]=lemma
				if lemma in freqs.keys():
					freqs[lemma]+=words.count(type)
				else:
					freqs[lemma]=words.count(type)
		self.freqs=freqs
	#2. go down list until reaching target
		globalfreqs=dict(zip(self.freqs.keys(),[0 for x in self.freqs.keys()]))
		for f in freqlist:
			if f in globalfreqs.keys():
				globalfreqs[f]=len(freqlist)-freqlist.index(f)
		sortable=[(self.freqs[x],globalfreqs[x],x) for x in self.freqs.keys()] 
		sortable.sort()
		sortable.reverse()
		self.sortable=sortable
		inc=0
		tolearn=list()
		learned_in_reading=set()
		lowerwords=[x for x in words if x.islower()]
		print len(words),len(lowerwords)
		while self.calculate_progress(lowerwords,self.freqs,tolearn,learned_in_reading) < target:
			try:
				thisword=sortable[inc][2]
			except IndexError:
				break
			tolearn.append(thisword)
			inc+=1
		self.tolearn=tolearn
		return tolearn
	
	def printout_list(self,path="C:\\Code\\ruwords-%s.txt" % datetime.date.today().isoformat()):
		file=open(path,"w")
		print path
		with file:
			for t in self.tolearn:
				file.write(t.encode("utf-8","ignore")+"\n")
	
	def calculate_progress(self,words,localfreqs,tolearn=set(),learned=set()):
		count=0
		for t in tolearn:
			if t in localfreqs.keys():
				count += localfreqs[t]
		progress=float(count)/float(len(words))
		print count, progress,len(words),len(localfreqs),len(tolearn)
		return progress


	def process_entry(self, entry,title):
		entry = entry.replace("== %s ==" % self.language,"==%s==" % self.language)
		if "==%s==" % self.language not in entry: return []
		section = entry.split("==%s==" % self.language)[1].split("----")[0].strip()
		if "\n#" not in section: return []
		if "===Declension" in section or "===Conjugation" in section or "===Inflection" in section:
			self.inflectiontables.add(title)
		senses = [x.split("\n")[0].strip() for x in section.split("\n#")[1:] if x[0] not in [":","*"]]
		return senses
	
	def get_forms(self):
		self.formdic={}
		for word in self.words.keys():
			senses=self.words[word]
			for sense in senses:
				formof=""
				if "{{form of|" in sense:
					pieces=sense.split("of|")[1].split("}}")[0].split("|")
					pieces=[x for x in pieces if "=" not in x]
					formof=pieces[-1]
				elif "of|" in sense:
					pieces=sense.split("of|")[1].split("}}")[0].split("|")
					pieces=[x for x in pieces if "=" not in x]
					formof=pieces[-1]
				elif "form of" in sense:
					formof=sense.split("form of")[1].split("]]")[0].replace("[[","").strip()
				elif " of''" in sense:
					formof=sense.split(" of'' ")[1].split("]]")[0].replace("'","").replace("[[","").strip()
				elif "of '''" in sense:
					formof=sense.split("of '''")[1].split("'''")[0].replace("'","").replace("[[","").replace("]]","").strip()
				if "{{l|ru|" in sense:
					formof=sense.split("{{l|ru|")[1].split("}}")[0]
					pieces=formof.split("|")
					formof=[x for x in pieces if "=" not in x][0]
				elif "{{term|" in sense:
					formof=sense.split("{{term|")[1].split("}}")[0]
					pieces=formof.split("|")
					formof=[x for x in pieces if "=" not in x][0]
				if formof:
					if word in self.forms.keys():
						self.formdic[word].append(formof)
					else:
						self.formdic[word]=[formof]

	def regularize(self):
		self.piewords = set()
		self.quickfind = {}
		lang = pie.Language(self.language)
		for word in self.tolearn:
			newword=pie.Word(word,language=lang)
			if word in self.words.keys():
				for gloss in self.words[word]:
					gloss = purify(gloss)
					if gloss in newword.glosses:
						continue
					else:
						newword.glosses.append(gloss)
			if newword.glosses:
				newword.gloss = newword.glosses[0].split(",")[0].split("(")[0].strip()
				if "}}" in newword.gloss:
					newword.gloss = newword.gloss.split("}}")[1]
			newword.glossed = "; ".join(newword.glosses)
			self.piewords.add(newword)
			self.quickfind[word] = newword
			print len(self.piewords)
		
	def is_form_of(self,sense,word):
		if "{{" in sense and " of|" in sense:
			pieces = sense.split("{{")[1].split("}}")[0].split("|")
			pieces = [purify(x).strip() for x in pieces]
			intersection = set(pieces).intersection(self.words)
			intersection -= set(["2","fut","simple","plural"])
			if intersection:
				if len(intersection) == 1:
					return list(intersection)[0]
				else: # hmmmm?
					print "Multiple suspects!", str(intersection)
					sortable=[(abs(len(x)-len(word)),x) for x in intersection]
					sortable.sort()
					return sortable[0][1]
			else: 
				sortable=[(abs(len(x)-len(word)),x) for x in pieces]
				sortable.sort()
				return sortable[0][1]
		elif "form of " in sense:
			return purify(sense.split("form of ")[1].strip().split(" ")[0].replace("[[","").replace("]]",""))

	def getdefs(wordlist=False,file="C:\\Code\\wikt.xml"):
		thispage=""
		reading=False
		output={} # dict of tuples
		file=open(file)
		for line in file:
				if "<page>" in line:
					reading=True
				if reading:
					thispage+=line+"\n"
				if "</page>" in line:
					reading=False
					if "=="+self.language not in thispage and "== "+self.language not in thispage:
						thispage=""
						continue
					thing=ET.XML(thispage)
					thispage=""
					title = thing.findtext("title")
					if ":" in title:
						continue
					entry = thing.find("revision").findtext("text")
					self.entries.add((title,entry))
					self.words.add(title)
					print len(self.words)


def purify(wikitext):
	out = wikitext.replace("[","").replace("]","")
	out = out.replace("'''","").replace("''","")
	out = out.replace("|"," ")
	out = out.split("#")[0]
	return out.strip()

def frequentize(text,lemmata, is_html=False): # lemmata is form-to-lemma dict
	text = text.decode("utf-8","ignore")
	freqs = {}
	tokens = text2words(text,is_html)
	wordset = set(tokens)-set(get_proper(tokens))
	print len(wordset)
	for w in wordset:
		if w in lemmata.keys():
			lemma = lemmata[w]
		elif w.lower() in wordset:
			if w.lower() in lemmata.keys():
				lemma = lemmata[w.lower()]
			else:
				lemma = w.lower()
		else:
			lemma = w
		if lemma in freqs.keys():
			freqs[lemma] += tokens.count(w)
		else:
			freqs[lemma] = tokens.count(w)
	return freqs

def get_proper(words):
	words = set(words)
	proper = [x for x in words if not x.islower() and x.lower() not in words]
	return set(proper)

def text2words(text, is_html=False):
	if type(text) == unicode:
		text=text.encode("utf-8","ignore")
	if is_html:
		# remove itals
		text = re.sub("\<i\>[^\<]+\<\/i\>", " ", text)
		text = re.sub("\<script[\s\S]+?\<\/script\>", " ", text)
		text = re.sub("\<.*?\>", "", text)
	for p in punx:
		text = text.replace(p," ")
	for p in pluspunx:
		text = text.replace(p," ")
	rawwords = [x for x in re.split("[\r\s\n\t]+",text) if x.strip()]
#	print len(rawwords)
	return rawwords


def clean_text_wiki(text):
		text=re.sub("\{\{[\s\S]+?\}\}"," ",text) # will fail badly on nested templates
		text=re.sub("\[\[.*?\|(.*?)\]\]","\\1",text)
		text=re.sub("\[[\S]+(.*?)\]","\\1",text)
		text=re.sub("\<.*?\>"," ",text)
		text=text.replace("[","")
		text=text.replace("]","")
		text=text.replace("'''","")
		text=text.replace("''","")
		text=text.strip()
		while text.startswith("*") or text.startswith(":") or text.startswith("#"):
			text=text[1:]
		return text

def get_sentences(text):
	sentencepattern = "([A-Z][a-z].+?\s[a-z][a-z][a-z]+[\?\!\.])[\s\r\n]"
	sentences = re.findall(sentencepattern,text)
	newsentences = []
	for s in sentences:
		try: 
			new = pie.unescape(s.decode("utf-8"))
			new = new.encode("utf-8")
		except (UnicodeDecodeError,UnicodeEncodeError):
			new = s
		newsentences.append(new)
	return newsentences

def process_sentences(allwords,newsentences,allforms=False,allsorted=False,wiki=False,href=""):
	modified=set()
	if not allforms:
		allforms=set(allwords)
	if not allsorted:
		allsorted=dict([(x,[]) for x in allwords])
	for n in newsentences:
		if wiki:
			n=clean_text_wiki(n) # scrub initial *, #, etc.
		inwords=set(text2words(n))
#		if len(inwords) > 10 or len(inwords) < 4: 
#			continue
#		else:
		dowords=inwords.intersection(allforms)
		for w in dowords:
#				allsorted[w].addsample(n,allwords,href=href)
			allsorted[w].append(n)
			modified.add(w)
#				print w, str(len(allsorted[w].examples))
	return modified,allsorted

def get_sentences2(text):
	if type(text) != unicode:
		text=text.decode("utf-8","ignore")
	enders=[u". ",u"?",u"!"]
	for e in enders:
		text=text.replace(e,e+"|||")
	text=text.replace(u"\n",u"\n|||")
	lines=[x.strip() for x in text.split("\n") if x.count("|||")>1]
	newtext="\n".join(lines)
	sentences=text.split(u"|||")
	sentences=[x.strip() for x in sentences if x.strip()]
	sentences=[x for x in sentences if x[-1] in enders]
	return sentences

def get_paragraphs(text):
	if type(text) == unicode:
		text=text.encode("utf-8","ignore")
	paragraphs=text.split("\n")
	paragraphs=[x.strip() for x in paragraphs if x.strip()]
	return paragraphs
	
def map_text(text,everyword,level=0.9, daily=100,prevwords=set()):
	if type(list(everyword)[0]) == unicode:
		everyword=set([x.encode("utf-8","ignore") for x in everyword])
	sentences=get_paragraphs(text)
	print len(text), len(sentences), sum([len(x) for x in sentences])
	chunks=[] # list of tuples of (chunk,set of words)
	index=0
	allwords=set(prevwords)
	while index < len(sentences):
		newwords=set()
		thischunk=[]
		while len(newwords-allwords) < daily and index < len(sentences):
			thischunk.append(sentences[index])
			newwords |= process_sentences(everyword,[thischunk[-1]])[0]
			print len(newwords), len(newwords-allwords)
			index+=1
		print index, len(chunks), len(thischunk)
		chunks.append((thischunk,newwords-allwords))
		allwords |= newwords
	return chunks
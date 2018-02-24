import datetime
import os 
import re
import pie
from string import punctuation as punx
import time
import urllib
import urllib2
import xml.etree.cElementTree as ET
# todo: 
# 1. harvest pos, pronunciation
# 2. fix "puis" -> "or"
# 3. ignore bad pos ("letter" &c.)
# 4. better handling of templates (context, gloss)

pluspunx=[unichr(x).encode("utf-8") for x in [171,187]]

class WiktiParser:
	def __init__(self):
		self.forms = {}
		self.words = {}
		self.entries = set()

	def process(self,file): # opened file object
		thispage = ""
		reading = False
		for line in file:
			if "<page>" in line:
				reading = True
			if reading is True:
				thispage += line+"\n"
			if "</page>" in line:
				if "==French" in thispage or "== French" in thispage:
					thing = ET.XML(thispage)
					reading = False
					thispage = ""
					title = thing.findtext("title")
					if ":" in title:
						continue
					entry = thing.find("revision").findtext("text")
					if title not in self.words.keys():
						self.words[title] = self.process_entry(entry)
					else: # main entry gets priority
						self.words[title] = self.process_entry(entry) + self.words[title]
					print len(self.words)
				if ("==English" in thispage or "== English" in thispage) and ("===Translations" in thispage or "=== Translations" in thispage):
					thing = ET.XML(thispage)
					reading = False
					thispage = ""
					title = thing.findtext("title")
					if ":" in title:
						continue
					entry = thing.find("revision").findtext("text")
					translations = re.findall("\{\{t[\+\-]*\|fr\|(.+?)[\|\}]",entry)
					if translations:
						try:
							print title,str(translations)
						except:
							pass
					for t in translations:
						if t in self.words.keys():
							self.words[t].append(title)
						else:
							self.words[t] = [title]
					print len(self.words)
				thispage = ""
				reading = False
				continue

	def process_entry(self, entry):
		entry = entry.replace("== French ==","==French==")
		if "==French==" not in entry: return []
		section = entry.split("==French==")[1].split("----")[0].strip()
		if "\n#" not in section: return []
		senses = [x.split("\n")[0].strip() for x in section.split("\n#")[1:] if x[0] not in [":","*"]]
		print len(senses)
		return senses
		
	def regularize(self):
		self.piewords = set()
		self.quickfind = {}
		lang = pie.Language("French")
		for word in self.words.keys():
			newword=pie.Word(word,language=lang)
			formonly = [self.is_form_of(x,word) for x in self.words[word]]
			formonly = [x for x in formonly if x]
			if formonly:
				formof = formonly[0]
				while formof[-1] in punx:
					formof = formof[:-1]
				if formof in self.forms.keys():
					self.forms[formof].append(word)
				else:
					self.forms[formof] = [word]
			else:
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
	if is_html:
		# remove itals
		text = re.sub("\<i\>[^\<]+\<\/i\>", " ", text)
		text = re.sub("\<script[\s\S]+?\<\/script\>", " ", text)
		text = re.sub("\<.*?\>", "", text)
	for p in punx:
		text = text.replace(p," ")
	rawwords = [x for x in re.split("[\r\s\n\t]+",text) if x.strip()]
	print len(rawwords)
	return rawwords

def getdefs(wordlist=False,file="C:\\Code\\enwikt.xml"):
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
				if "==French" not in thispage and "== French" not in thispage:
					thispage=""
					reading=False
					continue
				thing=ET.XML(thispage)
				reading=False
				thispage=""
				title = thing.findtext("title")
				if ":" in title:
					continue
				entry = thing.find("revision").findtext("text")
				self.entries.add((title,entry))
				self.words.add(title)
				print len(self.words)

class WikiCrawler:
	def __init__(self,words,allwords=False):
		self.words = words
		if allwords is False: self.allwords = words
		else: self.allwords = allwords
		self.text = ""
		self.sentences = 0
		self.entrycount = 0
		self.allforms = set()
		self.allsorted = dict()
		print "Spooling up..."
		for w in words:
			self.allforms |= set([x.encode("utf-8") for x in w.inflections])
			self.allsorted[w.mainform.encode("utf-8")] = w
			self.allsorted.update(dict([(x.encode("utf-8"),w) for x in w.inflections]))
		print len(self.allforms),len(self.allsorted),len(set(self.allwords).intersection(set(self.allsorted.values())))
	
	def crawl_wiki(self,dumppath,stop=0):
		file=open(dumppath)
		reading=False
		self.thispage=""
		self.modified=set()
		print "Starting..."
		self.wordlets=set(self.allsorted.values())
		for line in file:
			if "<page>" in line:
				reading=True
			if reading:
				self.thispage+=line+"\n"
			if "</page>" in line:
				thing=ET.XML(self.thispage)
				reading=False
				self.thispage=""
				self.title = thing.findtext("title")
				url = "http://fr.wikipedia.org/wiki/"+urllib.quote(self.title.encode("utf-8","ignore"))
				if ":" in self.title:
					continue
				self.entrycount += 1
				entry = thing.find("revision").findtext("text")
				self.text=clean_text_wiki(entry)
				self.newsentences=set(get_sentences(self.text))
				self.modified |= process_sentences(self.allforms,self.allsorted,self.allwords,self.newsentences,wiki=True,href=url)
				self.sentences += len(self.newsentences)
				print self.entrycount,self.sentences,len([x for x in self.wordlets if x.examples])
				if stop and stop < self.sentences:
					break
		return self.words


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

def process_sentences(allforms,allsorted,allwords,newsentences,wiki=False,href=""):
	modified=set()
	for n in newsentences:
		if wiki:
			n=clean_text_wiki(n) # scrub initial *, #, etc.
		inwords=set(text2words(n))
		if len(inwords) > 25 or len(inwords) < 3: 
#			print "continuing ", str(len(inwords))
			continue
		else:
			dowords=inwords.intersection(allforms)
#			print len(dowords)
			for w in dowords:
				allsorted[w].addsample(n,allwords,href=href)
				modified.add(w)
#				print w, str(len(allsorted[w].examples))
	return modified

def emergency_regularize(wparser):
		todo = set(wparser.words.keys()) - set(wparser.quickfind.keys())
		print "To do: ",str(len(todo))
		for word in todo:
			newword=pie.Word(word,language=lang)
			for gloss in wparser.words[word]:
				formof = wparser.is_form_of(gloss,word)
				if formof:
					if formof in wparser.forms.keys():
						wparser.forms[formof].append(word)
					else:
						wparser.forms[formof] = [word]
				else:
					gloss = purify(gloss)
					if gloss in newword.glosses:
						continue
					else:
						newword.glosses.append(gloss)
			if newword.glosses:
				newword.gloss = newword.glosses[0]
			wparser.piewords.add(newword)
			wparser.quickfind[word] = newword
			print len(wparser.piewords)
			
class Naverer:
	def __init__(self):
		pass
	
	def naver_loop(self,inpath,outpath="",directory="C:\\Code",limit=0,already=[],start=0):
		if not outpath:
			outpath=os.path.join(directory,"fr-defs-"+datetime.date.today().isoformat()+".txt")
		words=[x.split("\t")[0].strip() for x in open(inpath).read().split("\n")]
		print len(words)
		if limit:
			words=words[:limit]
		words=words[start:]
		words=set([x.strip() for x in words if x.strip()])
		self.output=""
		if already:
			words=words-set(already)
		words=list(words)
		self.words=words
		print len(words)
		for w in words:
			self.current=w
			done=False
			print words.index(w)
			while not done:
				try:
					defs=get_naver(w)
					time.sleep(5)
				except Exception, e:
					print str(e)
					time.sleep(10)
					continue
				done=True
			if defs:
				defs=[x.split("<")[0].replace("\t"," ") for x in defs] # should be HTML-free
				defstring=" //  ".join(defs)
				self.defs=defs
				self.defstring=defstring
				self.output+=w+"\t"+defstring+"\n"
			else:
				self.output+=w+"\t\n"
		if outpath:
			try:
				open(outpath,"w").write(self.output)
				print outpath
			except Exception, e:
				print str(e)
		outdefs=dict([tuple(x.split("\t")[:2]) for x in self.output.split("\n") if x.strip()])
		return outpath,outdefs
	
	def resume(self):
		pass
	
def get_naver(word):
	import urllib, urllib2
	url="http://frdic.naver.com/search.nhn?dic_where=krdic&query=%s&kind=keyword" % urllib.quote(word)
	page=urllib2.urlopen(url,timeout=100).read()
	if "<p>1." in page:
		print "1"
		defline=page.split("<p>1.")[1].split("</p>")[0]
		defline=defline.replace("&nbsp;"," ")
		defs=re.split("\d\d*\.",defline)
	elif '<button class="word_save save2wordbook_btn"' in page:
		print "3"
		defline=page.split('<button class="word_save save2wordbook_btn"')[0].split("<p>")[-1].split("</p>")[0]
		defs=re.split("\d\d*\.",defline)
	elif "<li><em>1.</em>" in page:
		print "2"
		chunk=page.split("<li><em>1.</em>")[1].split("</ol>")[0]
		defs=[x.split("</li>")[0] for x in chunk.split("</em>")]
	else:
		print "Not found!"
		defs=[]
	defs=[x.strip() for x in defs if x.strip()]
	return defs
	
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
		text=re.sub("([^\[])\[[^\[][\S]+(.*?)\]","\\1\\2",text)
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

'''def process_sentences(allwords,newsentences,allforms=False,allsorted=False,wiki=False,href=""):
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
'''

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
	
class WikiScavenger:
	def __init__(self,start=False,path="C:\\enwikt.xml",basicpath="C:\\Code\\gougenheim-1.txt"):
		if start:
			self.load_basic_words(basicpath)
			self.load(path)
		else:
			pass

	def load_basic_words(self,basicpath):
		self.basicpath=basicpath
		basix=open(basicpath).read().split("\n")
		basix = [x.split("\t")[0] for x in set(basix) if x]
		basix = [x.strip() for x in basix if x.strip()]
		self.basic_words = set(basix)
		print len(self.basic_words)

	def load(self,path="",everything=False):
		self.wiktipath=path
		if not everything:
			self.everything=WiktiParser()
			self.everything.process(open(path))
		else:
			self.everything.regularize()
			self.everything=everything
		self.quickfind=dict([(x,self.everything.quickfind[x]) for x in self.everything.quickfind.keys() if x in self.basic_words])
		self.piewords=self.quickfind.values()
		self.formdic={}
		for word in self.everything.forms.keys():
			if word not in self.basic_words: # keep this in fighting trim
				continue
			else:
				for form in self.everything.forms[word]:
					if form not in self.formdic.keys():
						self.formdic[form]=[word]
					else:
						self.formdic[form].append(word)

	
	def scavenge(self,dumppath):
		self.crawler=WikiCrawler(self.piewords)
		meh=self.crawler.crawl_wiki(dumppath)
		return meh

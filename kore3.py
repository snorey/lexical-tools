# -*- coding: utf-8 -*-

import datetime
import os
import re
import time
import urllib2
from htmlentitydefs import name2codepoint
from string import punctuation as punct

import pie
import kore4

workingdir = pie.workingdir
filepath=os.path.join(workingdir,"koverbs.txt")
global verbage

try:
	print len(verbage)
except NameError:
	print "resetting verbage..."
	verbage=set()
moreverbs=[]

class Syllable:
	vowels=["a","ae","ya","yae","eo","e","yeo","ye","o","wa","wae","oe","yo","u","wo","we","wi","yu","eu","ui","i"]
	initials=["g","kk","n","d","tt","r","m","b","pp","s","ss","#","j","jj","ch","k","t","p","h"]
	finals=["#","g","kk","ks","n","nj","nh","d","l","lk","lm","lb","ls","lt","lp","lh","m","b","bs","s","ss","ng","j","ch","k","t","p","h"]
	raw=""
	def __init__(self,text):
		self.raw=text
		if type(text) == str:
			try: text=unicode(text,"utf-8")
			except UnicodeDecodeError: text=unicode(text,"cp949")
		text=text.strip()
		self.text=text
		if len(text) != 1:
			raise LengthError
		self.number=ord(text)
		if self.number < 44032 or self.number > 55203: 
#			print self.number
#			raise TypeError
			self.rom=""
		else:
			self.number-=44032
			self.consonumber=int(self.number/588)
			self.endnumber=self.number % 28
			self.vowelnumber=int((self.number % 588)/28)
			self.rom=".".join([self.initials[self.consonumber],self.vowels[self.vowelnumber],self.finals[self.endnumber]])
	
	def __str__(self):
		return self.rom
		
class LengthError(Exception):
	def __init__(self):
		print "Syllable is too short or too long!"
		
class koWord(pie.Word):
	def __init__(self,text,vocab,parser=False):
		pie.Word.__init__(self,text=text)
		self.syllables=[]
		self.stemmed=""
		self.aporiai=[]
		self.raw=text
		if type(text) == str:
			try: text=unicode(text,"utf-8")
			except UnicodeDecodeError: text=unicode(text,"cp949")
#		if parser:
		self.parser=parser
#		self.parser=parser
#		else:
#			self.parser=Parser("",False)
		text=text.strip()
		self.text=text
		self.vocab=vocab
		self.hangul=-1
		for t in text:
			if ord(t) < 44032 or ord(t) > 55203:
				self.hangul=self.hangul * 2
				self.syllables.append((0,t))
			else:
				self.hangul=abs(self.hangul)
				self.syllables.append((1,Syllable(t)))
		if self.hangul % 2: #if still odd, no non-Kore script chars
			self.hangul=True
			self.mixed=False
		elif self.hangul > 0: #non-Kore script chars, but also Kore
			self.hangul=True
			self.mixed=True
		else:
			self.hangul=False
			self.mixed=False
		self.rom=self.romanize()
#		if self.rom not in self.vocab.quickfind.keys():
#			self.process()

	def __len__(self):
			return len(self.syllables)
			
	def process(self,noun=[],firstpass=True,restrict=False,thisform=""):
		if not self.hangul: 
			try:
				print "not hangul",self.text
			except:
				pass
			return self.text
		if self.mainform == self.rom:
			self.rom=self.romanize()
		if not thisform: thisform=self.rom
		if thisform in self.vocab.quickfind.keys(): # if in the reference vocabulary, don't stem further.
			self.stemmed=thisform
			self.inflections.add(self.rom)
			self.inflections.add(thisform)
			return thisform
		verbs=dict(verbage)
		try:
			if not self.syllables[-1][0]: 
				return self.text
		except IndexError:
			return self.text
		self.notdone=False
		afterparticles=""
		if len(self.syllables) > 1:
			if thisform.endswith("#---r.eu.l") and firstpass: #object
				if thisform[:-2] not in verbs.keys(): # .. .
					self.stemmed=thisform[:-9]
				else:
					self.stemmed=thisform[:-1]+"#---d.a.#"
			elif thisform.endswith("---#.eu.l") and firstpass:
					if not thisform.endswith("#---#.eu.l"):
						self.stemmed=self.rom[:-9]
			elif thisform.endswith("#---g.a.#"): #subject
				if thisform.endswith("---d.a.#---g.a.#"):
					self.stemmed=self.rom[:-16]+"---d.a.#"
				else:
					self.stemmed=self.rom[:-8]
			elif thisform.endswith("---#.i.#"):
				if not thisform.endswith("#---#.i.#"):
						self.stemmed=thisform[:-8]
			elif thisform.endswith("#---n.eu.n") and firstpass: #topic
				if thisform[:-9] not in verbs.keys() and thisform[:-10]+"l" not in verbs.keys() and firstpass:
					self.stemmed=thisform[:-9]
				elif thisform[:-9] in verbs.keys():
					self.stemmed=thisform[:-9]
				elif thisform[:-10]+"l" in verbs.keys():
					self.stemmed=thisform[:-10]+"l"
			elif thisform.endswith("---#.eu.n") and firstpass:
				if not thisform.endswith("#---#.eu.n"):
						self.stemmed=thisform[:-9]
						self.notdone=True
			elif thisform.endswith("---r.o.#"): 
				self.stemmed=self.rom[:-8]
				if thisform.endswith("---#.eu.#---r.o.#"):
					if not thisform.endswith("#---#.eu.#---r.o.#"):
							self.stemmed=thisform[:-17]
			elif thisform.endswith("#---r.o.#---s.eo.#"):
				self.stemmed=thisform[:-17]
				if thisform.endswith("---#.eu.#---r.o.#---s.eo.#"):
					if not thisform.endswith("#---#.eu.#---r.o.#---s.eo.#"):
							self.stemmed=thisform[:-26]
			elif thisform.endswith("#---r.o.#---ss.eo.#"): 
				self.stemmed=thisform[:-18]
				if thisform.endswith("---#.eu.#---r.o.#---ss.eo.#"):
					if not thisform.endswith("#---#.eu.#---r.o.#---ss.eo.#"):
							self.stemmed=thisform[:-27]
			elif thisform.endswith("---#.e.#"):
				self.stemmed=thisform[:-8]
			elif thisform.endswith("---#.e.#---g.e.#"):
				self.stemmed=thisform[:-16]
			elif thisform.endswith("---kk.e.#"):
				self.stemmed=thisform[:-9]
			elif thisform.endswith("---#.e.#---s.eo.#"):
				self.stemmed=thisform[:-17]
			elif thisform.endswith("---kk.e.#---s.eo.#"):
				self.stemmed=thisform[:-18]
			elif thisform.endswith("---kk.a.#---j.i.#"):
				self.stemmed=thisform[:-17]
			elif thisform.endswith("---b.u.#---t.eo.#"):
				self.stemmed=thisform[:-17]
			elif thisform.endswith("---#.ui.#") and firstpass: # correct for stuff like ..
				self.stemmed=thisform[:-9]
			elif thisform.endswith("---d.eu.l"):
				self.stemmed=thisform[:-9]
			elif thisform.endswith("---#.i.n"):
				self.stemmed=thisform[:-8]
			elif thisform.endswith("#---#.wa.#"):
				self.stemmed=thisform[:-9]
			elif thisform.endswith("---g.wa.#") and not thisform.endswith("#---g.wa.#"):
					self.stemmed=self.rom[:-9]
			elif thisform.endswith("---d.o.#"):
				self.stemmed=thisform[:-8]
			elif thisform.endswith("---m.a.n"):
				self.stemmed=thisform[:-8]
			elif thisform.endswith("---ch.eo.#---r.eo.m"):
				self.stemmed=thisform[:-19]
			elif thisform.endswith("---m.a.l---#.ya.#"):
				self.stemmed=thisform[:-17]
			afterparticles=self.stemmed
			if afterparticles != thisform:
				nounish=True
			else:
				nounish=False
			if self.stemmed not in self.vocab.quickfind.keys():
				if self.stemmed.endswith("d.oe.#"): #cleanup
					self.stemmed=self.stemmed[:-9]
				elif not nounish:
					if self.stemmed:
						self.stemmed=suggestoverb(self.stemmed,verbs,self.vocab)
					else:
						self.stemmed=suggestoverb(thisform,verbs,self.vocab)
				else:
					thelist=["---g.i.#","m"]
					self.stemmed=suggestoverb(thisform,verbs,self.vocab,thelist)
		if not self.stemmed: 
			self.stemmed=self.rom
		if self.stemmed in verbs.keys():
			if not self.stemmed == afterparticles or not len(self.stemmed.split("---")) < 2:
				self.stemmed=verbs[self.stemmed]
		elif self.stemmed.endswith("#.i.#---d.a.#") and len(self.stemmed) > 16: # assuming not a verb in its own right, attached copula
			self.stemmed=self.stemmed[:-16]
		if firstpass and self.stemmed != self.rom:
			self.process(firstpass=False,thisform=self.stemmed,restrict=restrict)
			after_one=str(self.stemmed)
		self.inflections=set([self.rom,self.stemmed])
		return self.stemmed
		

	def romanize(self):
		try:
			output="---".join([str(Syllable(x)) for x in self.mainform])
			return output
		except TypeError:
			return ""
		except LengthError:
			return ""

class Parser:
	def __init__(self,text,vocab):
		self.rawwords=False
		self.words=False
		self.text=text
		self.vocab=vocab
		if self.vocab == False:
			self.vocab=pie.Vocabulary()
		if text:
			print "Processing..."
			self.process(text)
	
	def len(self):
		return len(self.text)

	def __str__(self):
		text=self.text
		if type(text) == unicode:
			text=text.encode("utf-8","ignore")
		return text

	def romanize(self,word):
		if type(word) != unicode: word=unicode(word,"utf-8","ignore")
		word=word.strip()
		output="---".join([str(Syllable(x)) for x in word])
		return output
				
	def process(self,text):
		self.text=text
		from string import punctuation
		for p in punctuation: text=text.replace(p," ")
		if type(text) == str:
			try: text=unicode(text,"utf-8")
			except UnicodeDecodeError: text=unicode(text,"cp949")
		self.rawwords=[x for x in re.split("[\s\r\n\t]+",text) if x.strip()]
		print len(self.rawwords)
		self.words=set()
		for w in self.rawwords:
			self.words.add(koWord(w,parser=self,vocab=self.vocab))
		print len(self.words)
		self.stems=[(x,x.process()) for x in self.words]
		print len(self.stems)
		self.stems=[x for x in self.stems if x[0]]
		return self.stems
		
def chosun(date=datetime.date.today()):
	datestring=date.isoformat().replace("-","")
	directory="C:\\Corp\\KO\\Chosun\\"+datestring
	try:
		os.mkdir(directory)
	except: 
		pass
	already=set(os.listdir(directory))
	starturl="http://news.chosun.com/svc/list_in/list_title.html?indate="+datestring
	startpage=False
	while not startpage:
		try:
			startpage=urllib2.urlopen(starturl,timeout=10).read()
			time.sleep(1)
		except:
			print "Error!!!"
			time.sleep(5)
	articles=set()
	articles|=chosun_process_page(startpage)
	morecounter=2
	theresmore=1
	while theresmore:
		moreurl='http://news.chosun.com/svc/list_in/list_title.html?indate=%s&pn=' % datestring 
		moreurl+=str(morecounter) 
		print moreurl
		try: 
			morepage=urllib2.urlopen(moreurl,timeout=10).read()
			time.sleep(1)
		except:
			print "Error..."
			time.sleep(5)
			continue
		newarticles=chosun_process_page(morepage)
		articles|=newarticles
		theresmore=len(newarticles)
		morecounter+=1
		time.sleep(1)
	articles=list(articles)
	for a in articles:
		url="http://news.chosun.com/site/data/html_dir/"+a
		print url, articles.index(a),len(articles)
		filename=a.split("/")[-1]
		if filename in already: continue
		try:
			articlepage=urllib2.urlopen(url,timeout=10).read()
		except:
			print "Error!"
			time.sleep(5)
			continue
		writefile=open(os.path.join(directory,filename),"w")
		with writefile:
			writefile.write("<url>%s</url>" % url)
			writefile.write(articlepage)

			
def chosun_process_page(page=""):
	matcher='\<dt\>\<span id\=\"tit\"\>\<a href\=\"\/site\/data\/html_dir\/([0-9\/\.]+\.html)"\s*\>'
	articles=set(re.findall(matcher,page))
	print str(len(articles))
	return articles
	
def chosun_get_text(rawtext=""):
	catchers=[('articleArea">',''),
		("<!-- article -->",""),
		('<ul class="article" id="fontSzArea">','</ul>'),
		('<div id="ArticlePar01"',''),
		]
	text=u""
	for c in catchers:
		catchme=c[0]
		endme=c[1]
		if catchme in rawtext:
			break
	if catchme in rawtext:
		text=rawtext.split(catchme)[1].strip()
		if endme:
			text=rawtext.split(endme)[0].strip()
	try:
		url=rawtext.split("<url>",1)[1].split("</url>")[0]
		rawtext=rawtext.replace(url,"")
	except IndexError:
		url=""
	text=re.sub("\<script[\s\S]+\<\/script\>","",text)
	text=re.sub("\<.*?\>"," ",text)
	text=re.sub("[\r\n\s\t]+"," ",text)
	text=text.decode("euc-kr","ignore")
	text=unescape(text)
	text=text.strip()
	text=text.encode("utf-8","ignore")
	return (url,text)
	
def chosun_aggregate(directory):
	outfile=open(os.path.join(directory,"agg.txt"),"w")
	with outfile:
		for file in os.listdir(directory):
			if not file.endswith(".html"): continue
			filetext=open(os.path.join(directory,file)).read()
			texttuple=chosun_get_text(filetext)
			if not texttuple:
				print "Empty file!!!",file
				continue
			outfile.write("\n<url>%s</url>\n%s\n" % texttuple)

def chosun_agg_all(start=""):
	dirs=os.listdir("/home/calumet/KO/news/Chosun")
	if start:
		dirs=dirs[dirs.index(start):]
	print len(dirs)
	dirs=[os.path.join("/home/calumet/KO/news/Chosun",x) for x in dirs]
	dirs.sort()
	for d in dirs:
		print d
		chosun_aggregate(d)


class Peruser:
	def __init__(self,wordlist=[],limit=0,gonow=False):
		self.wordlist=wordlist
		self.simplewords=wordlist
		self.currentdir=""
		if limit:
			self.simplewords=wordlist[:limit]
		if gonow: self.chosun_peruse(wordlist)

	def chosun_peruse(self,wordlist=[],start="",directory="C:\\Corp\\KO\\Chosun"): # going for examples only here...
# needed for this to work: full integration of kore3.Word and pie.Word
		if not wordlist: wordlist=self.wordlist
		dirs=os.listdir(directory)
		if start:
			dirs=dirs[dirs.index(start):]
		dirs=[os.path.join(directory,x) for x in dirs]
		dirs.sort()
		stems=dict([(x.stemmed,x) for x in wordlist])
		for d in dirs:
			if "agg.txt" not in os.listdir(d): continue
			print d
			self.currentdir=d
			aggtext=open(os.path.join(d,"agg.txt")).read()
			if not aggtext: continue
			aggtext=aggtext.decode("utf-8","ignore")
			stems=process_aggtext(aggtext,stems,self.simplewords)
		return self.wordlist

def process_aggtext(aggtext,stems,wordlist):
	pieces=[tuple([x.strip() for x in y.split("</url>")]) for y in aggtext.split("<url>")[1:]]
	for p in pieces:
		url=p[0]
		text=p[1]
		dummyvoc=pie.Vocabulary()
		sentences=get_sentences(text)
		sentences=[x for x in sentences if len(x.split(" ")) < 10] # eliminate long ones
		sentences=[Parser(text=x,vocab=dummyvoc) for x in sentences]
		for s in sentences:
			sentems=[x[1] for x in s.stems]
			matches=set(sentems).intersection(set(stems.keys()))
			if not matches: continue
			for m in matches:
				stems[m].addsample(s.text,wordlist,href=url.encode("utf-8","ignore"))
	return stems

def get_sentences(text):
	if type(text) != unicode:
		text=text.decode("utf-8","ignore")
	enders=[u". ",u"? ",u"! ",u'." ']
	for e in enders:
		text=text.replace(e,e+u"|||")
	sentences=text.split(u"|||")
	sentences=[x.strip() for x in sentences]
	sentences=[x for x in sentences if x]
	return sentences

def kookje(date=datetime.date.today()):
	datestring=date.isoformat().replace("-","")
	urlstring="http://www.kookje.co.kr/news2006/asp/search.asp?sort=d&sv=%s&ev=%s&a1=SVC_DATE&sp=%s&cmts_yn=Y"
	starturl=urlstring % (datestring,datestring,"0")
	directory="/home/calumet/KO/news/Kookje/"+datestring
	try:
		os.mkdir(directory)
	except: 
		pass
	already=set(os.listdir(directory))
	startpage=False
	while not startpage:
		try:
			startpage=urllib2.urlopen(starturl,timeout=20).read()
			time.sleep(1)
		except:
			print "Error!!!"
			time.sleep(5)
	articles=set()
	articles|=kookje_process_page(startpage)
	morecounter=1
	moreincrement=10
	theresmore=1
	while theresmore:
		moreurl=urlstring % (datestring,datestring,morecounter*moreincrement)
		print moreurl
		try: 
			morepage=urllib2.urlopen(moreurl,timeout=20).read()
			time.sleep(1)
		except:
			print "Error..."
			time.sleep(5)
			continue
		newarticles=kookje_process_page(morepage)
		articles|=newarticles
		theresmore=len(newarticles)
		morecounter+=1
		time.sleep(1)
	articles=list(articles)
	for a in articles:
		url="http://www.kookje.co.kr/news2006/asp/"+a
		print url, str(articles.index(a)), str(len(articles))
		filename=a.split("key=")[1].split("&")[0]+".html"
		if filename in already: continue
		try:
			articlepage=urllib2.urlopen(url,timeout=20).read()
		except:
			print "Error!"
			time.sleep(5)
			continue
		writefile=open(os.path.join(directory,filename),"w")
		with writefile:
			writefile.write("<url>%s</url>" % url)
			writefile.write(articlepage)

def kookje_process_page(page=""):
	matcher='\<a href\=\"(center\.asp\?.*?)\"'
	articles=re.findall(matcher,page)
	articles=set([x.replace("&amp;","&") for x in articles])
	print str(len(articles))
	return articles

def frequentize(text,vocab):
	freqs={}
	words=text2words(text)
	lemmata=process_text(text,vocab)
	for w in set(words):
		lemma=lemmata[w]
		if lemma in freqs.keys():
			freqs[lemma]+=words.count(w)
		else:
			freqs[lemma]=words.count(w)
	return freqs

def unescape(text): 
#From code by Fredrik Lundh at http://effbot.org/zone/re-sub.htm#-html
# Licensed to the public domain at http://effbot.org/zone/copyright.htm
# Seems to work better than BeautifulSoup for this purpose
	def fixup(m):
		text = m.group(0)
		if text[:2] == "&#":
			try:
				if text[:3] == "&#x":
					return unichr(int(text[3:-1], 16))
				else:
					return unichr(int(text[2:-1]))
			except ValueError:
				pass
		else:
			try:
				text = unichr(name2codepoint[text[1:-1]])
			except KeyError:
				pass
		return text
	return re.sub("\&\#?\w+\;", fixup, text)

def romanize(word):
	if type(word) != unicode: word=unicode(word,"utf-8","ignore")
	word=word.strip()
	syllables=[Syllable(x) for x in word if x.strip()]
	syllables=[str(x) for x in syllables if x.rom]
	output="---".join(syllables)
	if re.match("\w+",word) and not syllables:
		output=word.encode("utf-8","ignore")
	return output

def process_oo(lines):
	outlines=set()
	for line in lines:
		broken=line.split("/")
		if len(broken) < 2: 
			broken+=[""]
		broken[0]=romanize_jamo(broken[0])
		if broken[0]:
			outlines.add(tuple(broken))
	return outlines

def romanize_jamo(word): # For inputs in Unicode jamo rather than syllabic blocks
	initials=["g","kk","n","d","tt","r","m","b","pp","s","ss","#","j","jj","ch","k","t","p","h"]
	vowels=["a","ae","ya","yae","eo","e","yeo","ye","o","wa","wae","oe","yo","u","wo","we","wi","yu","eu","ui","i"]
	finals=["g","kk","ks","n","nj","nh","d","l","lk","lm","lb","ls","lt","lp","lh","m","b","bs","s","ss","ng","j","ch","k","t","p","h"]
	if type(word) != unicode: word=unicode(word,"utf-8","ignore")
	word=word.strip()
	chars=list(word)
	syllables=[]
	currentsyll=""
	for c in chars:
		codepoint=ord(c)
		if 4351 < codepoint < 4371:
			rom=initials[codepoint-4352]
			if currentsyll.endswith("."): # ended in jungseong?
				syllables.append(currentsyll+"#")
			currentsyll=rom+"."
		elif 4448 < codepoint < 4470:
			rom=vowels[codepoint-4449]
			currentsyll+=rom+"."
		elif 4519 < codepoint < 4547:
			rom=finals[codepoint-4520]
			currentsyll+=rom
			syllables.append(currentsyll)
		else:
			break
	if syllables:
		if currentsyll != syllables[-1]:
			if currentsyll.endswith("."): # ended in jungseong?
				syllables.append(currentsyll+"#")
			else:
				syllables.append(currentsyll)
	return "---".join(syllables)

def get_verb_forms(romstem,romverb):
	forms=[romstem]
	polite=""
	polite1="" #unkludge this
	if not romstem.endswith("#"): # consonant
		extra=romstem+"---#.eu.#"
		forms.append(extra)
		if romstem.endswith(".s"):
			alt=romstem[:-1]+"#---#.eu.#"
			forms.append(alt)
		elif romstem.endswith(".p"):
			alt=romstem[:-1]+"#---#.u.#"
			forms.append(alt)
			polite=romstem[:-1]+"#---#.wo.#"
			forms.append(polite)
		elif romstem.endswith(".d"):
			alt=romstem[:-1]+"r"
			forms.append(alt)
			themevowel=romstem[-3]
			polite=romstem[:-1]+"r---#.%s.#" % themevowel
			forms.append(polite)
	elif romstem.endswith(".i.#"):
		polite1=romstem+"#.eo.#"
		polite2=romstem[:-3]+"yeo.#"
		forms.append(polite1)
		forms.append(polite2)
	elif romstem.endswith(".u.#"):
		polite1=romstem+"---#.eo.#"
		polite2=romstem[:-3]+"wo.#"
		forms.append(polite1)
		forms.append(polite2)
	elif romstem.endswith("h.a.#"):
		polite1=romstem+"---#.yeo.#"
		polite2=romstem[:-3]+"ae.#"
		forms.append(polite1)
		forms.append(polite2)
	elif romstem.endswith("d.oe.#"):
		polite1=romstem+"---#.eo.#"
		polite2=romstem[:-4]+"wae.#"
		forms.append(polite1)
		forms.append(polite2)
	elif romstem.endswith(".e.#") or romstem.endswith(".ae.#"):
		forms.append(romstem+"---#.eo.#")
	elif romstem.endswith(".l"):
		forms.append(romstem[:-1]+"#")
	elif romstem.endswith("#---r.eu.#"):
		polite=romstem.replace("#---r.eu.#","l---r.a.#")
		forms.append(polite)
	if not romstem.endswith("#"):
		themevowel=romstem.split(".")[-2]
		if themevowel in ["a","ya","o","yo","wa"]:
			polite=romstem+"---#.a.#"
		else:
			polite=romstem+"---#.eo.#"
		forms.append(polite)
	if romstem.endswith(".o.#"):
		polite=romstem[:-3]+"wa.#"
		forms.append(polite)
	if polite:
		past=polite[:-1]+"ss"
		forms.append(past)
	elif polite1:
		past1=polite1[:-1]+"ss"
		past2=polite2[:-1]+"ss"
		forms.append(past1)
		forms.append(past2)
	else: # polite = mainform
		past=romstem[:-1]+"ss"
		forms.append(past)
	forms=set(forms)
	return forms

def process_verb(romstem,romverb):
	polite1=""
	polite2=""
	polite=""
	global verbage
	verbage.add((romstem,romverb)) #have to use list of tuples, not dict, to guard against overlaps
	if not romstem.endswith("#"): # consonant
		extra=romstem+"---#.eu.#"
		verbage.add((extra,romverb))
		if romstem.endswith(".s"):
			alt=romstem[:-1]+"#---#.eu.#"
			verbage.add((alt,romverb))
		elif romstem.endswith(".p"):
			alt=romstem[:-1]+"#---#.u.#"
			verbage.add((alt,romverb))
			polite=romstem[:-1]+"#---#.wo.#"
			verbage.add((polite,romverb))
		elif romstem.endswith(".d"):
			alt=romstem[:-1]+"r"
			verbage.add((alt,romverb))
			themevowel=romstem[-3]
			polite=romstem[:-1]+"r---#.%s.#" % themevowel
			verbage.add((polite,romverb))
	elif romstem.endswith(".i.#"):
		polite1=romstem+"#.eo.#"
		polite2=romstem[:-3]+"yeo.#"
		verbage|=set([(polite1,romverb),(polite2,romverb)])
	elif romstem.endswith(".u.#"):
		polite1=romstem+"---#.eo.#"
		polite2=romstem[:-3]+"wo.#"
		verbage|=set([(polite1,romverb),(polite2,romverb)])
	elif romstem.endswith("h.a.#"):
		polite1=romstem+"---#.yeo.#"
		polite2=romstem[:-3]+"ae.#"
		verbage|=set([(polite1,romverb),(polite2,romverb)])
		if romstem.replace("---h.a.#","---d.oe.#") not in romverbs:
			moreverbs.append(romstem.replace("---h.a.#","---d.oe.#"))
	elif romstem.endswith("d.oe.#"):
		polite1=romstem+"---#.eo.#"
		polite2=romstem[:-4]+"wae.#"
		verbage|=set([(polite1,romverb),(polite2,romverb)])
	elif romstem.endswith(".e.#") or romstem.endswith(".ae.#"):
		verbage.add((romstem+"---#.eo.#",romverb))
	elif romstem.endswith(".l"):
		verbage.add((romstem[:-1]+"#",romverb))
	elif romstem.endswith("#---r.eu.#"):
		polite=romstem.replace("#---r.eu.#","l---r.a.#")
		verbage.add((polite,romverb))
	if not romstem.endswith("#"):
		themevowel=romstem.split(".")[-2]
		if themevowel in ["a","ya","o","yo","wa"]:
			polite=romstem+"---#.a.#"
		else:
			polite=romstem+"---#.eo.#"
		verbage.add((polite,romverb))
	if romstem.endswith(".o.#"):
		polite=romstem[:-3]+"wa.#"
		verbage.add((polite,romverb))
	if polite:
		past=polite[:-1]+"ss"
		verbage.add((past,romverb))
	elif polite1:
		past1=polite1[:-1]+"ss"
		past2=polite2[:-1]+"ss"
		verbage|=set([(past1,romverb),(past2,romverb)])
	else: # polite = mainform
		past=romstem[:-1]+"ss"
		verbage.add((past,romverb))
	return (polite1,polite2,polite)


def suggestoverb(thisform,verbs,vocab,thelist=False):
	maybestem=""
	if not thelist: thelist=[
			"---m.a.#",
			"---d.o.#---r.o.g",
			"---j.i.#---m.a.n",
			"---m.eu.#---r.o.#",
			"---d.eo.#---n.i.#",
			"---d.eo.#---r.a.#",
			"b---n.i.#---d.a.#",
			"b---s.i.#---d.a.#",
			"b---s.i.#---#.o.#",
			"---s.i.#---#.o.#",
			"---g.eo.#---n.a.#",
			"---g.eo.#---n.i.#---.wa.#",
			"---d.a.n---d.a.#",
			"---d.a.#",
			"---d.a.n",
			"---#.yo.#",
			"---g.eo.#---d.eu.n",
			"---g.o.#",
			"---g.u.#",
			"---r.a.#",
			"---r.i.#",
			"---n.i.#",
			"---n.a.#",
			"---j.a.#",
			"---s.e.#",
			"---s.eo.#",
			"---m.yeo.n",
			"---m.yeo.#",
			"---d.eo.n",
			"---d.eu.n",
			"---d.eu.s",
			"---#.eu.#---m.yeo.#",
			"---g.u.#---n.a.#",
			"---g.u.n",
			"---g.e.ss---#.eu.#",
			"---g.e.ss---#.eo.#",
			"---g.e.ss",
			"n---d.a.#",
			"---n.eu.n---d.e.#",
			"---r.eo.#",
			"---r.yeo.#",
			"ss---d.a.#",
			"ss---d.a.#---g.o.#",
			"---g.e.#",
			"l---kk.a.#",
			"l---kk.e.#",
			"---j.i.#",
			"---#.eu.n",
			"---n.eu.n",
			"---#.ya.#",
			"l",
			"n",
			"m",
			"---g.i.#",
			"---j.i.#",
			"---j.yeo.#",
			"---j.yeo.ss",
			"---#.eo.ss",
			"---s.i.#",
			"---s.yeo.#",
			"---s.yeo.ss",
			"---d.a.#",
# adjuncts
			"---b.o.#",
			"---b.wa.#",
			"---b.o.#---#.a.ss",
			"---b.wa.ss",
			"---b.eo.#---r.i.#",
			"---b.eo.#---r.yeo.#",
			"---b.eo.#---r.yeo.ss",
			"---j.u.#---#.eo.#",
			"---j.wo.#",
			"---j.u.#",
			"---j.u.#---#.eo.ss",
			"---j.wo.ss",
			"---#.i.ss",
			"---#.i.ss---#.eu.#",
			"---#.i.ss---#.eo.#",
			"xxx",
	]
	stemmed=thisform
	for ending in thelist:
		if thisform.endswith(ending):
			maybestem=thisform[:-len(ending)]
			if not ending.startswith("---"):
				maybestem+="#"
			thisform=maybestem
			print maybestem
			if maybestem in verbs.keys():
				stemmed=verbs[maybestem]
				break
		elif ending=="xxx": #finished cycle
			if not verbs or not maybestem:
				pass
			else:
				if maybestem in verbs.keys():
					stemmed=verbs[maybestem]
				elif maybestem.endswith("---#.i.#"): # copula
					if maybestem[:-8] in vocab.quickfind.keys():
						stemmed=maybestem[:-8]
				elif maybestem.endswith("#---d.a.#"): #elided copula
					if maybestem[:-8] in vocab.quickfind.keys():
						stemmed=maybestem[:-8]
				elif maybestem.endswith("---s.eu.#---r.eo.#"):
					stemmed=maybestem[:-18]
				elif maybestem.endswith("---s.eu.#---r.eo.#---#.u.#"):
					stemmed=maybestem[:-26]
	return stemmed
	
def text2words(text):
	rawwords=[]
	splitter="[%s]" % re.escape(punct)+"\r\r\n\t"	
	for x in re.split(splitter,text):
		if not x.strip(): continue
		try:
			rawwords.append(romanize(x))
		except TypeError:
			continue
		except LengthError:
			continue
#	words=set(rawwords)
#	return words
	return rawwords

def text2romwords(text):
	splitter="[%s\r\n\t\s]+" % re.escape(punct)
	words=set(re.split(splitter,text))
	romwords=[romanize(x) for x in words]
	return set(romwords)

	
def process_text(text,vocab=False,callme=False): # text must be Unicode
	words=set(text2words(text))
	lemmata=dict([(x,x) for x in words])
	print len(lemmata)
	nounage=find_nouns(words)
	if vocab:
		todo=words-set(vocab.quickfind.keys())
	else:
		todo=words
	k=0
	for t in todo:
		if callme is not False: # callback function for progress meter
			callme(k,len(todo))
			k+=1
		lemmata[t]=process_word(t,vocab)
	return lemmata

def find_nouns(wordset):
	nounage=set()
	for word in wordset:
		if word+"---d.eu.l" in wordset:
			nounage.add(word)
		elif word.endswith("#"):
			if word+"---g.a.#" in wordset and not word.endswith("---d.a.#"):
				nounage.add(word)
			elif word+"---r.eu.l" in wordset:
				nounage.add(word)
			elif word+"---r.o.#" in wordset:
				nounage.add(word)
		elif not word.endswith("h"): # avoid trickery of johda, anhda &c.
			if word+"---#.i.#" in wordset:
				nounage.add(word)
			elif word+"---#.eu.l" in wordset:
				if word not in dict(verbage).keys():
					nounage.add(word)
			elif word+"---#.eu.#---r.o.#" in wordset:
				nounage.add(word)
	return nounage

def process_word(word,vocab=False,noun=[],firstpass=True,restrict=False,thisform=""): # romanized word
		if not thisform: thisform=word
		stemmed=thisform
		verbs=dict(verbage)
		notdone=False
		afterparticles=""
		nounish=False
		if vocab is False: 
			vocab=pie.Vocabulary()
		if len(word.split("---")) > 1: # syllable count
			if thisform.endswith("#---r.eu.l") and firstpass: #direct object
				if thisform[:-2] not in verbs.keys(): # ...
					stemmed=thisform[:-9]
				else:
					stemmed=thisform[:-1]+"#---d.a.#"
			elif thisform.endswith("---#.eu.l") and firstpass:
					if not thisform.endswith("#---#.eu.l"):
						stemmed=word[:-9]
			elif thisform.endswith("#---g.a.#"): #subject
				if thisform.endswith("---d.a.#---g.a.#"):
					stemmed=word[:-16]+"---d.a.#"
				else:
					stemmed=word[:-8]
			elif thisform.endswith("---#.i.#"):
				if not thisform.endswith("#---#.i.#"):
						stemmed=thisform[:-8]
			elif thisform.endswith("#---n.eu.n") and firstpass: #topic
				if thisform[:-9] not in verbs.keys() and thisform[:-10]+"l" not in verbs.keys() and firstpass:
					stemmed=thisform[:-9]
				elif thisform[:-9] in verbs.keys():
					stemmed=thisform[:-9]
				elif thisform[:-10]+"l" in verbs.keys():
					stemmed=thisform[:-10]+"l"
			elif thisform.endswith("---#.eu.n") and firstpass:
				if not thisform.endswith("#---#.eu.n"):
						stemmed=thisform[:-9]
						notdone=True
			elif thisform.endswith("---r.o.#"): 
				stemmed=word[:-8]
				if thisform.endswith("---#.eu.#---r.o.#"):
					if not thisform.endswith("#---#.eu.#---r.o.#"):
							stemmed=thisform[:-17]
			elif thisform.endswith("#---r.o.#---s.eo.#"):
				stemmed=thisform[:-17]
				if thisform.endswith("---#.eu.#---r.o.#---s.eo.#"):
					if not thisform.endswith("#---#.eu.#---r.o.#---s.eo.#"):
							stemmed=thisform[:-26]
			elif thisform.endswith("#---r.o.#---ss.eo.#"): 
				stemmed=thisform[:-18]
				if thisform.endswith("---#.eu.#---r.o.#---ss.eo.#"):
					if not thisform.endswith("#---#.eu.#---r.o.#---ss.eo.#"):
							stemmed=thisform[:-27]
			elif thisform.endswith("---#.e.#"):
				stemmed=thisform[:-8]
			elif thisform.endswith("---#.e.#---g.e.#"):
				stemmed=thisform[:-16]
			elif thisform.endswith("---#.e.#---g.e.#---s.eo.#"):
				stemmed=thisform[:-25]
			elif thisform.endswith("---kk.e.#"):
				stemmed=thisform[:-9]
			elif thisform.endswith("---#.e.#---s.eo.#"):
				stemmed=thisform[:-17]
			elif thisform.endswith("---kk.e.#---s.eo.#"):
				stemmed=thisform[:-18]
			elif thisform.endswith("---kk.a.#---j.i.#"):
				stemmed=thisform[:-17]
			elif thisform.endswith("---b.u.#---t.eo.#"):
				stemmed=thisform[:-17]
			elif thisform.endswith("---#.ui.#") and firstpass: # correct for stuff like ..
				stemmed=thisform[:-9]
			elif thisform.endswith("---d.eu.l"):
				stemmed=thisform[:-9]
			elif thisform.endswith("---#.i.n"):
				stemmed=thisform[:-8]
			elif thisform.endswith("#---#.wa.#"):
				stemmed=thisform[:-9]
			elif thisform.endswith("---g.wa.#") and not thisform.endswith("#---g.wa.#"):
					stemmed=word[:-9]
			elif thisform.endswith("---d.o.#"):
				stemmed=thisform[:-8]
			elif thisform.endswith("---ch.eo.#---r.eo.m"):
				stemmed=thisform[:-19]
			elif thisform.endswith("---m.a.n"):
				stemmed=thisform[:-8]
			elif thisform.endswith("---m.a.l---#.ya.#"):
				stemmed=thisform[:-17]
			if stemmed.endswith("---d.eu.l"):
				if stemmed[:-1]+"#" not in verbs.keys():
					stemmed=stemmed[:-9]
			afterparticles=stemmed
			if afterparticles != thisform:
				nounish=True
			if stemmed not in vocab.quickfind.keys():
				if stemmed.endswith("d.oe.#"): #cleanup
					stemmed=stemmed[:-9]
				elif not nounish:
					if stemmed:
						stemmed=suggestoverb(stemmed,verbs,vocab)
					else:
						stemmed=suggestoverb(thisform,verbs,vocab)
				else:
					thelist=["---g.i.#","m"]
					stemmed=suggestoverb(stemmed,verbs,vocab,thelist)
		if stemmed in verbs.keys():
			if not stemmed == afterparticles or not len(stemmed.split("---")) < 2:
				stemmed=verbs[stemmed]
		elif stemmed.endswith("#.i.#---d.a.#") and len(stemmed) > 16: # assuming not a verb in its own right, attached copula
			stemmed=stemmed[:-16]
		return stemmed

def collect_examples_chosun(wordlist,path="C:\\Corp\\KO\\Chosun"):
	examples=dict([(x,set([])) for x in wordlist])
	dirs=os.listdir(path)
	for d in dirs:
		print d
		fullpath=os.path.join(path,d)
		if "agg.txt" not in os.listdir(fullpath):
			continue
		else:
			aggpath=os.path.join(fullpath,"agg.txt")
			newsamples=grab_examples(wordlist,open(aggpath).read())
			newsamples=dict([(x,newsamples[x]) for x in newsamples.keys() if newsamples[x]])
#			newsamples=grab_examples_chosun(wordlist,aggpath)
			for n in newsamples.keys():
					print n
					examples[n] |= newsamples[n]
	return examples

def grab_examples_chosun(wordlist,aggpath): # currently bypassed
	aggtext=open(aggpath).read()
	examples=dict([(x,set([])) for x in wordlist])
	articles=[tuple(x.split("</url>")) for x in aggtext.split("<url>") if x.strip()]
	for a in articles:
		print a[0], str(len(a[1]))
		newsamples=grab_examples(wordlist,a[1])
		updates=[x for x in newsamples.keys() if newsamples[x]]
		print len(updates)
		for u in updates:
			print u
			examples[u] |= newsamples[u]
	output=dict([(x,examples[x]) for x in examples.keys() if examples[x]])
	return output

class Getter:
	def __init__(self,inpath,start=True):
		import kore4
		self.inpath=inpath
		if start:
			self.defpath=kore4.naver_ko_loop(inpath)[0]
		else:
			self.defpath=self.inpath

	def step2(self,outpath="C:\\Code\\ko-ready-"+datetime.date.today().isoformat()+".txt",defpath=False): #after manual refiltering of defs
		if defpath:
			self.defpath=defpath
		self.outpath=outpath
		lines=open(self.defpath).read().split("\n")
		self.defs2=dict([tuple(x.split("\t",1)) for x in lines if x.strip()])
		words=self.defs2.keys()
		self.words=words
		self.romwords=[romanize(x) for x in words]
		self.chosun=collect_examples_chosun(self.romwords)
		self.chosun=sift_examples(self.chosun)
		self.naver=dict([(x,kore4.get_examples_naver(x)) for x in self.words])
		self.naver=sift_examples(self.naver)
		self.examples=dict([(x,[]) for x in self.words])
		for w in self.words:
			if self.chosun[romanize(w)]:
				if self.naver[w]:
					self.examples[w]=self.chosun[romanize(w)][:2]+self.naver[w][:2]
					self.examples[w]=self.examples[w][:3]
				else:
					self.examples[w]=self.chosun[romanize(w)][:3]
			else:
				self.examples[w]=self.naver[w][:3]
			self.examples[w]=self.examples[w]+["","",""]
			self.examples[w]=self.examples[w][:3]
		self.output="\n".join([x+"\t"+self.defs2[x]+"\t"+("\t".join(self.examples[x])) for x in self.words])
		open(outpath,"w").write(self.output)
		return outpath

def sift_examples(exampledict,limit=3,minlength=5,maxlength=100,whitelist=[]):
	output={}
	for e in exampledict.keys():
		sortable=[(len(unicode(x,"utf-8","ignore")),x) for x in set(exampledict[e])]
		sortable.sort()
		sortable=[x for x in sortable if x[0] >= minlength and x[0] <= maxlength]
		output[e]=[x[1] for x in sortable][:limit]
	return output
	
def grab_examples(wordlist,text): # list or set of romanized words, UTF-8 encoded text
	text=text.decode("utf-8","ignore")
	examples=dict([(x,set([])) for x in wordlist])
	wordage=[(x,x) for x in wordlist]
	verbs=[x for x in wordlist if x.endswith("---d.a.#")]
	notverbs=set(wordlist)-set(verbs)
	for v in verbs:
		forms=get_verb_forms(v[:-8],v)
		formed=[(x,v) for x in forms if len(x.split("---")) > 1]
		wordage.extend(formed)
	for n in notverbs:
		if n.endswith("#"): # no batchim
			particles=["#.e.#","g.a.#","r.eu.l","n.eu.n","#.e.#---g.e.#","r.o.#"]
		else:
			particles=["#.e.#","#.i.#","#.eu.l","#.eu.n","#.e.#---g.e.#","#.eu.#---r.o.#"]
		formed=[(n+"---"+x,n) for x in particles]
		wordage.extend(formed)
	wordfinder=dict(wordage) # form:lemma
	textwords=text2romwords(text)
	cleanmatches=set(wordfinder.keys()).intersection(textwords)
	cleanmatches=[x for x in cleanmatches if x.strip()]
	dirtymatches=[]
#	dirtymatches=[x for x in wordfinder.keys() if [y for y in textwords if y.startswith(x)]]
	if not cleanmatches and not dirtymatches:
		print "Zilch."
	else:
		print len(cleanmatches)
		for c in cleanmatches:
			if not c.strip(): continue
			pieces=re.split(u"(\W"+hangulize(c)+u"\W)",text,1)
			if len(pieces) < 3:
				continue
			center=pieces[1]
			before=pieces[0]+center[0]
			before=before.split(".")[-1]
			before=before[::-1] #reverse
			before=re.split("[\r\n\t\!\.\?]",before,1)[-1] 
			before=before[::-1] #unreverse
			if "</url>" in before:
				before=before.split(">",1)[1]
			after=pieces[2]+center[-1]
			after=after.split(".")[0]+"."
			after="".join(re.split("([\r\n\t\!\.\?]+[\s\"\']*)",after,1)[0:2])
			sentence=before+hangulize(c)+after
			if len(sentence) < len(c)*2:
				continue
			elif len(sentence) > len(c)*20:
				continue
			keyword=wordfinder[c]
			examples[keyword].add(sentence.encode("utf-8","ignore"))
		for d in dirtymatches:
			pass
	return examples

def hangulize(romword):
	syllables=romword.split("---")
	vowels=["a","ae","ya","yae","eo","e","yeo","ye","o","wa","wae","oe","yo","u","wo","we","wi","yu","eu","ui","i"]
	initials=["g","kk","n","d","tt","r","m","b","pp","s","ss","#","j","jj","ch","k","t","p","h"]
	finals=["#","g","kk","ks","n","nj","nh","d","l","lk","lm","lb","ls","lt","lp","lh","m","b","bs","s","ss","ng","j","ch","k","t","p","h"]
	output=u""
	for s in syllables:
		pieces=s.split(".")
		first=pieces[0]
		vowel=pieces[1]
		last=pieces[2]
		number=44032+(588*initials.index(first))
		number+=28*vowels.index(vowel)
		number+=finals.index(last)
		output+=unichr(number)
	return output

	
def setup():
### keep at end ###
	if not verbage:
		try:
			file=open(filepath)
		except IOError:
			pass
		else:
			with file:
				rawverbs=[unicode(x.split(":")[0],"utf-8","ignore").strip() for x in file if ":" in x]
			romverbs=[]
			for r in rawverbs:
					romverbs.append(romanize(r[:-1]))
			for v in rawverbs:
				romstem=romanize(v[:-1])
				romverb=romanize(v)
				process_verb(romstem,romverb) # adds to verbage.
		print "Done with verbs."

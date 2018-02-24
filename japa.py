# -*- coding: utf-8 -*-

'''
Todo

File handling - Xish
Upload to server 
Update from server
Web interface
Vocab editor (bulk word removal, etc.) X
-- need to handle adding new words, kana, rom
-- need sorting, filtering
Progress info X
-- need to integrate onto main page
Dynamic ranking of examples by simplicity relative to consolidated and in-progress vocab
Vocab tester - X
implementation of vocab test results 
On each card: indicator of past experiences, importance; for practice cycle, number of past attempts in this cycle
Ability to fine-tune examples (uprate, downrate, delete, add)
Ability to fine-tune definitions, glosses - X
User notes(dismissable) - groundwork
Text integration, suggested readings
Pasteboard functionality - groundwork
Hrefs for examples - laid groundwork
Improve exclusions using soundex, SensEval prioritization
Vocabulary notebook functionality with bonus features from server
On the fly editability

Codebase:
break into language-neutral sections and language settings files
basic language functions/classes: Word(), ListBuilder(), lemmatize(), tokenize(), Downloader()

'''

import os, re
import datetime, time
import urllib2, urllib
import unicodedata, random
# import threading
from htmlentitydefs import name2codepoint

# Third-party modules
import wx
import wx.lib.agw.piectrl
import wx.lib.scrolledpanel
from nltk.corpus import wordnet as wn
from nltk.corpus import stopwords
from nltk.metrics import edit_distance as distance

import romaji
from tinysegmenter import TinySegmenter
import xmlreader #PyWikipedia

# globals

wordmatcher='(?<=\W)[a-z][a-z\-]+[a-z](?=\W)'
stops=set(stopwords.words("english"))
segmenter=TinySegmenter()

class JaWord:
	def __init__(self,line="",maxgloss=3,maxsample=10,user=False):
		self.line=line
		self.maxsample=maxsample
		if user:
			self.user=user
		else:
			self.user=User()
		if not line:
			lineparts=["","","",""]
		else:
			lineparts=re.findall("(.*?) \[(.*?)\] \/\((.*?)\) (.+)",line.strip())
			if lineparts: lineparts=lineparts[0]
		if not lineparts: 
			if "[" not in line:
				self.mainform=line.split("/")[0].strip()
				self.kana=self.mainform
			else:
				self.mainform=line.split("[")[0].strip()
				self.kana=line.split("[")[1].split("]")[0]
				if "(" in self.kana or u"（" in self.kana:
					self.kana=self.mainform
			try: 
				self.pos=line.split("(")[1].split(")")[0]
			except IndexError:
				self.pos=""
			if self.mainform.startswith("~"):
				self.pos="suffix"
				self.mainform=self.mainform[1:]
			elif self.mainform.endswith("~"):
				self.pos="prefix"
				self.mainform=self.mainform[:-1]
			if "/" in line:
				self.glossed=line.split("/",1)[1]
			else:
				self.glossed=""
		else: 
			self.mainform=lineparts[0].strip()
			kanaform=lineparts[1].strip()
			if u"(" in kanaform or u"（" in kanaform or not kanaform:
				self.kana=self.mainform
			else:
				self.kana=kanaform
			self.pos=lineparts[2].strip()
			self.glossed=lineparts[3].replace("(P)","")
		self.rom=romaji.roma(self.kana).lower()	
		self.glossed=re.sub("\(.*?\)"," ",self.glossed).strip()
		self.glosses=[x.strip() for x in self.glossed.split("/") if x][:maxgloss]
		if self.glosses:
			gloss=self.glosses[0]
		else:
			self.gloss=""
		self.examples=[]
		self.keyed=[]
		self.inflections=set([self.mainform])
		self.tally=0 # number of occurrences in corpus
		self.successes=[] # number of successful learnings in current pass
		self.failures=[]
		self.history=[]
		self.notes=[]
		self.sequestered=False
		self.status=1 #available
		
	def __str__(self):
		return self.rom
		
	def count(self):
		return len(self.successes)
		
	def succeed(self,sessionid=0,is_practice=False):
		timestamp=time.time()
		if not is_practice:
			self.successes.append((timestamp,sessionid))
			self.history.append((1,timestamp,sessionid))
		else:
			self.history.append((10,timestamp,sessionid))
		
	def fail(self,sessionid=0):
		timestamp=time.time()
		self.failures.append((timestamp,sessionid))
		self.history.append((0,timestamp,sessionid))
		self.successes=[] # restart the clock...
	
	def skip(self,sessionid=0):
		timestamp=time.time()
		self.history.append((-1,timestamp,sessionid))
	
	def inflect(self):
		if not self.pos.startswith("adj") and not self.pos.startswith("v"): 
			return False
		queryurl="http://en.wiktionary.org/wiki/"+urllib.quote(self.mainform.encode("utf-8"))
		txdata=''
		txheaders={'User-agent' : 'Mozilla/4.0 (compatible; MSIE 5.5; Windows NT)'}
		req=urllib2.Request(queryurl,txdata,txheaders)
		querypage=urllib2.urlopen(req).read()
		newforms=re.findall('lang\=\"ja\-Jpan\"\>(.+?)\<\/td\>',querypage)
		if not newforms:
			newforms=[x.split("</td>")[0] for x in querypage.split("<td>")[1:] if "</td>" in x]
		try: 
			newforms=[x.split(">")[1].split("<")[0] for x in newforms]
			newforms=[x.decode("utf-8","ignore") for x in newforms]
			newforms=[x.strip() for x in newforms if x.strip()]
			newforms=[x for x in newforms if not re.search("[a-zA-Z]",x)]
		except: 
			return False
		print len(newforms),self.rom
		self.inflections=list(self.inflections)
		self.inflections.extend(newforms)
		self.inflections=set(self.inflections)

	def addsample(self,sample,words):
		if type(sample) == str or type(sample) == unicode:
			sample=Example(sample)
		self.tally+=1
		if not self.keyed:
			self.keyed=[(simplicity(str(x),words),x) for x in self.examples]
		if re.search("[a-zA-Z]",str(sample)): 
			print self.rom,str(sample).encode("cp949","ignore")
			return False
		testsample=str(sample).replace(" ","")[:-1] # remove terminal punct.
		if testsample in [str(x)[:-1] for x in self.examples]: return False
		if len(testsample)/len(self.mainform) < 2 and len(self.mainform) < 4: 
			return False
		if len(testsample)-len(self.mainform) < 3: 
			return False
		if len(testsample.replace(self.mainform,"")) < 3: return False
		else:
			self.keyed.append((simplicity(str(sample),words),sample))
			self.keyed=list(set(self.keyed)) 
			self.keyed.sort()
			self.keyed.reverse()
			self.keyed=self.keyed[:self.maxsample]
			self.examples=[x[1] for x in self.keyed]
			return True

# dump to pseudo-XML
	def dump(self,all=False,indented="\t",singleindent="\t",encoding="utf-8"): #pseudo-XML fragment
		outstring=indented+'<Word name="%s" status="%s" user="%s">\n' % (self.mainform.encode(encoding,"ignore"),str(self.status),str(self.user))
		outstring+=indented+singleindent+'<Romanization>%s</Romanization>\n' % self.rom.encode(encoding,"ignore")
		outstring+=indented+singleindent+'<Kana>%s</Kana>\n' % self.kana.encode(encoding,"ignore")
		outstring+=indented+singleindent+'<Gloss>%s</Gloss>\n' % self.gloss.encode(encoding,"ignore")
		outstring+=indented+singleindent+'<Glossed>%s</Glossed>\n' % self.glossed.encode(encoding,"ignore")
		outstring+=indented+singleindent+'<Sequestered>%s</Sequestered>\n' % str(self.sequestered)
		if self.line:
			outstring+=indented+singleindent+'<Line>%s</Line>' % self.line.encode(encoding,"ignore")
		outstring+=indented+singleindent+'<Examples>\n'
		for e in self.examples:
			outstring+=indented+singleindent+singleindent+'<Example>%s</Example>\n' % e.encode(encoding)
		outstring+=indented+singleindent+'</Examples>\n'
		outstring+=indented+singleindent+'<History>\n'
		for h in self.history:
			outstring+=indented+singleindent+singleindent+'<Event value="%s" session="%s">%s</Event>\n' % (str(h[0]),str(h[2]),str(h[1]))
		outstring+=indented+singleindent+'</History>\n'
		outstring+=indented+singleindent+'<Successes>\n'
		for s in self.successes:
			outstring+=indented+singleindent+singleindent+'<Event value="1" session="%s">%s</Event>\n' % (str(s[1]),str(s[0]))
		outstring+=indented+singleindent+'</Successes>\n'
		outstring+=indented+singleindent+'<Notes>\n'
		for s in self.notes:
			outstring+=indented+singleindent+singleindent+'<Note type="%s" session="%s">%s</Note>\n' % (str(s[1]),str(s[2]),str(s[0]))
		outstring+=indented+singleindent+'</Notes>\n'
		outstring+=indented+singleindent+'<Inflections>\n'
		for i in self.inflections:
			outstring+=indented+singleindent+singleindent+'<Form>%s</Form>\n' % i.encode(encoding,"ignore")
		outstring+=indented+singleindent+'</Inflections>\n'
		outstring+=indented+"</Word>"
		return outstring

# Command line interface
	def cardform(self,reverse=False):
		if not reverse:
			cardform=self.mainform.encode("cp949","ignore")
			if cardform.decode("cp949","ignore") != self.mainform: print "Warning!!!"
			cardform+="\n\nKana: "+self.kana.encode("cp949","ignore")
			cardform+="\n\nExamples: "+"\n".join([x.encode("cp949","ignore") for x in self.examples])
			cardform+="\n\n"+self.mainform.encode("cp949","ignore")
			return cardform
		else:
			cardform=self.gloss
	
	def addnote(self,text="",session=time.time(),type=""):
		self.notes.append((type,session,user,text))

def wordcloud(definition): #generates a cloud of associated words from a definition string
		words=set(re.findall("[a-zA-Z\-]+",definition))-stops
		synsets=[]
		cloud=set()
		for w in words:
			synsets.extend(wn.synsets(w))
			for synset in synsets:
				output=[]
				lemmata=synset.lemmas
				try: output.append(synset.holonyms())
				except AttributeError: pass
				try: output.extend(synset.hypernyms())
				except AttributeError: pass
				try: output.extend(synset.meronyms())
				except AttributeError: pass
				try: output.extend(synset.troponyms())
				except AttributeError: pass
				try: output.extend(synset.hyponyms())
				except AttributeError: pass
			# now, get synonyms
				output.extend([str(x).split(".")[-1][:-2] for x in lemmata])
				for ell in lemmata:
					output.extend(ell.antonyms())  # don't want antonyms, probably...
					output.extend(ell.derivationally_related_forms())
					output.extend(ell.pertainyms())
				newout=[str(x).replace('_'," ") for x in output if "Synset" not in str(x) and "Lemma" not in str(x)]
				newout.extend([str(x).split(".")[0][8:].replace("_"," ") for x in output if "Synset" in str(x)])
				newout.extend([str(x).split(".")[0][7:].replace("_"," ") for x in output if "Lemma" in str(x)])
				output=newout
				cloud|=set(output)
		return cloud


def sortem(words=[],segment=100,groups=False,maxoverlap=1,tooclose=0.3,definitions=[]): # words may either be a flat wordlist or a dict of definitions
# or a list oftuples withthe the first item being a sequence key and the second the word itself
	print len(words)
	if not groups:
		print "Fresh start"
		groups=[Group(segment,tooclose=tooclose)]
	if type(words) == list:
		pass
	else:
		defined=words
		words=words.keys()
	if type(words[0]) != tuple:
		wordlist=[(words.index(x),x) for x in words]
	else:
		wordlist=words
	wordlist.sort()
	print len(wordlist)
	for word in wordlist:
		w=word[1]
		print str(w),str(len(groups))
		needmore=True
		for g in groups:
			neighbors=[]
			index=groups.index(g)
			if index > 0:
				neighbors.append(groups[index-1])
			if index > len(groups)-1:
				neighbors.append(groups[index+1])
			if g.ok2add(w,maxoverlap=maxoverlap):
				if False in [x.ok2add(w,maxoverlap=maxoverlap,worry_about_length=False) for x in neighbors]: 
					continue
				needmore=False
				if defined:
					g.add(w,defined[word],tupled=word)
				else:
					g.add(w,tupled=word)
				break
		if needmore:
			newgroup=Group(segment,set([w]),tooclose=tooclose)
			if defined:
				newgroup.glosses=set([defined[word]])
				newgroup.wordcloud=wordcloud(defined[word])
			newgroup.storage.add(word)
			groups.append(newgroup)
	return groups

class Example:
	def __init__(self,text="",href="",priority=0,encoding=None):
		self.text=text
		self.priority=priority
		self.href=href
		self.encoding=encoding
	
	def __len__(self):
		return len(self.text)
		
	def __str__(self):
		return self.encodeme("utf-8")
		
	def encodeme(self,encoding=None):
		if encoding:
			if not self.encoding:
				return self.text.encode(encoding,"ignore")
			else:
				return self.text.decode(self.encoding,"ignore").encode(encoding,"ignore")
		else:
			if not self.encoding:
				return self.text
			else:
				return self.text.decode(self.encoding,"ignore")
			
class Project:
	def __init__(self,level=4,preloaded=False,reset=False):
		if not preloaded:
			self.page=open("D:\\Code\\jlpt-voc-%s-extra.euc" % str(level)).read()
			self.words=ebdic(self.page)
			for w in self.words:
				try:
					w.inflect()
				except:
					print "Error on "+w.rom,w.glossed
		else: # when loading from another project or list
			self.page=""
			self.words=[]
			for p in preloaded:
				newp=JaWord(p.line)
				newp.inflections=p.inflections
				if not reset:
					newp.examples=p.examples
					newp.tally=p.tally
				self.words.append(newp)
					
	def exem(self):
		self.words=crawl_asahi(self.words)
		self.words=crawl_wikis(self.words)
	
	def dump(self,path="D:\\japa.txt",groupsize=20):
		self.groups=sortem(self.words,groupsize)
		self.wordsout=sortemout(self.groups)
		self.output=indexit(self.wordsout,path)

		
def revalidate(words): #utility to clean up examples when updating code
	for w in words:
		proxy=JaWord() # blank word for dummy testing
		proxy.mainform=w.mainform
		proxy.examples=list(w.examples)
		examples=list(w.examples)
		for e in set(examples):
			try:
				proxy.examples.remove(e)
				proxy.addsample(e,words)
				print "OK ",w.rom
			except:
				print "Error! ",w.rom
		w.examples=list(proxy.examples)


def asahi(date=datetime.date.today()):
	directory="D:\\Corp\\Asahi\\Asahi_"+date.isoformat()
	try: os.mkdir(directory)
	except: pass
	already=os.listdir(directory)
	numdate=date.isoformat().split("-",1)[1].replace("-","")
	starturl="http://www.asahi.com/news/daily/%s.html" % numdate
	print starturl
	page=urllib2.urlopen(starturl).read()
	indexfile=open(os.path.join(directory,"index.html"),"w")
	with indexfile:
		indexfile.write(page)
	urlpieces=re.findall('href\=\"([a-zA-Z0-9\-\_\/]*?\/%s\/.*?\.html)' % numdate,page)
	urls=set(["http://www.asahi.com/"+x for x in urlpieces if not x.startswith("/")])|set(["http://www.asahi.com"+x for x in urlpieces if x.startswith("/")])
	print len(urls)
	for u in urls:
		filename=u.split("/")[-1]
#		print filename
		if filename in already: continue
		try: 
			page=urllib2.urlopen(u).read()
		except:
			time.sleep(3)
			try: 
				page=urllib2.urlopen(u).read()
			except:
				print "unable to open "+u
				continue
		time.sleep(1)
		print filename
		file=open(os.path.join(directory,filename),"w")
		with file:
			try: 
				file.write(page)
			except:
				print "Unable to write "+filename

				
def crawl_asahi(words):
	directory="D:\\Corp\\Asahi"
	directories=set(os.listdir(directory))
	allforms=set()
	allsorted=dict()
	for w in words:
		allforms|=w.inflections
		allsorted.update(dict([(x,w) for x in w.inflections]))
		allforms=set([x for x in allforms if x])
	for d in directories:
		print d
		files=set([os.path.join(directory,d,x) for x in os.listdir(os.path.join(directory,d))])
		for f in files:
			text=get_text_asahi(f)
			sentences=get_sentences(text)
			process_sentences(allforms,allsorted,words,sentences)
	return words

def get_text_asahi(filepath):
	file=open(filepath).read()
	try:
		text=file.split('<div class="BodyTxt">')[1].split("</div>")[0]
		text=text.decode("euc-jp","ignore")
		text=unescape(text)
		text=re.sub(u"\<style[\s\S]+?\<\/style\>"," ",text)
		text=re.sub(u"\<script[\s\S]+?\<\/script\>"," ",text)
		text=re.sub(u"\<\!\-\-[\s\S]+?\-\-\>"," ",text)
		text=text.replace(u"<p>"," ")
		text=re.sub(u"\<.*?\>"," ",text)
	except IndexError:
		text=u""
	return text
	
def get_frequencies(text,already={}):
	tokens=segmenter.tokenize(text)
	for t in set(tokens):
		if t in already.keys():
			already[t]+=tokens.count(t)
		else:
			already[t]=tokens.count(t)
	return already

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

def purge(wordlist):
	newlist=[]
	for w in wordlist:
		if type(w) != unicode: raise TypeError
		w=w.encode("utf-8","ignore").decode("utf-8","ignore").strip()
		problem=[unicodedata.category(x) for x in w if not unicodedata.category(x).startswith("L")]
		if problem:
			print w.encode("cp949","ignore"),str(problem)
		else:
			newlist.append(w)
	return newlist
	

def ebdic(text):
	words=[]
	lines=text.split("\n")
	for line in lines:
		line=line.strip()
		if not line: continue
		if line.startswith("#"): continue
		line=line.decode("euc-jp","ignore")
		words.append(JaWord(line))
	return words

def sortem(words,size=100,maxoverlap=1,tooclose=0.3): # List of JaWord objects for sorting
	sort_freq=[(x.tally,100.0/(1.0+words.index(x)),x) for x in words] #prioritize -- first by frequency, second by initial ranking
	sort_freq.sort()
	sort_freq.reverse()
	words=[x[2] for x in sort_freq]
	defined=dict([((words.index(x),x.rom),"".join(x.glosses[:1])) for x in words])
	romanized=dict([((words.index(x),x.rom),x) for x in words]) #store info for  de-romanizing after sort
	import indo
	sorted=indo.sortem(defined,size,tooclose=tooclose,maxoverlap=maxoverlap)
	for group in sorted:
		group.members=set([romanized[x] for x in group.storage]) #de-romanize
	return sorted


def sortemout(groups):
	allthewords=[]
	for g in groups:
		allthewords.extend(g.members)
	return allthewords
		
def crawl_wikis(words,allwords="",extensions=["bz2"],stop=0):
	if not allwords: allwords=words
	text=""
	sentences=0
	dumps=[x for x in os.listdir("D:\\Code") if x.startswith("jawik") and x.split(".")[-1] in extensions]
	allforms=set()
	allsorted=dict()
	for w in words:
		allforms|=w.inflections
		allsorted.update(dict([(x,w) for x in w.inflections]))
		allforms=set([x for x in allforms if x])
	for d in dumps:
		try:
			print d
			dump=xmlreader.XmlDump(os.path.join("D:\\Code",d))
			for entry in dump.parse():
#				text+="\n\n"+entry.text
				text=clean_text_wiki(entry.text)
				newsentences=set(get_sentences(text))
				process_sentences(allforms,allsorted,allwords,newsentences,wiki=True)
				sentences+=len(newsentences)
				if stop and stop < sentences:
					return words
				print d,sentences
		except KeyboardInterrupt:
			return words
		except MemoryError:
			return words
	return words

def get_sentences(text):
	enders=[u"。",u"？",u"！",u". ",u"?",u"!"]
	for e in enders:
		text=text.replace(e,e+"|||")
	text=text.replace(u"\n",u"\n|||")
	lines=[x.strip() for x in text.split("\n") if x.count("|||")>1]
	newtext="\n".join(lines)
	sentences=text.split(u"|||")
	sentences=[x.strip() for x in sentences if x.strip()]
	sentences=[x for x in sentences if x[-1] in enders]
	return sentences

def process_sentences(allforms,allsorted,allwords,newsentences,wiki=False):
	for n in newsentences:
		if len(n[:-1].strip().split(" ")) > 10: continue
		elif len(n[:-1].strip().split(" ")) < 3: continue
		if wiki:
			n=clean_text_wiki(n) # scrub initial *, #, etc.
		theseforms=set([x for x in allforms if x in n])
		if not theseforms: continue
		for w in theseforms:
			if segmenter.tokenize(w)[0] in segmenter.tokenize(n): #final sanity check
				allsorted[w].addsample(n,allwords)

def clean_text_wiki(text):
		text=re.sub("\{\{[\s\S]+\}\}"," ",text)
		text=re.sub("\[\[.*?\|(.*?)\]\]","\\1",text)
		text=re.sub("\[[\S]+(.*?)\]","\\1",text)
		text=re.sub("\<.*?\>"," ",text)
		text=text.replace("[[","")
		text=text.replace("]]","")
		text=text.strip()
		while text.startswith("*") or text.startswith(":") or text.startswith("#"):
			text=text[1:]
		return text
			
def simplicity(sentence,wordset):
	if not sentence.strip(): return 0
	allforms=set()
	for w in wordset:
		allforms|=w.inflections
	oldlength=len(sentence)
	for a in allforms:
		if not a: continue
		if type(a) == str: 
			a=a.decode("utf-8","ignore")
		if a in sentence: 
			sentence=sentence.replace(a," ")
	sentence=sentence.replace(" ","")
	newlength=len(sentence)
	simplicity=100*(float(oldlength-newlength)/float(oldlength) ** 1.5) # slight penalty for length
	return simplicity

def indexit(words,path="D:\\japa.txt"):
	output=""
	for word in words:
		samples="\t".join(word.examples)
		output+=u"%s\t%s\t%s\t%s\t%s\n" % (word.mainform,word.kana,word.rom," / ".join(word.glosses),samples)
	outfile=open(path,"w")
	with outfile:
		try: 
			outfile.write(output.encode("utf-8","ignore"))
		except:
			print "Error!"
	return output
	

def restore(filepath):
	words=[]
	file=open(filepath)
	for line in file:
		line=line.strip()
		if line.count("\t") < 3: continue
		line=line.decode("utf-8","ignore")
		lineparts=line.split("\t")
		word=JaWord()
		word.mainform=lineparts[0]
		word.kana=lineparts[1]
		word.rom=lineparts[2]
		word.glossed=lineparts[3]
		word.glosses=lineparts[3].split(" / ")
		try: 
			word.gloss=word.glosses[0]
			word.gloss=re.sub("\(.*?\)"," ",word.gloss).strip()
		except IndexError:
			word.gloss=""
		word.examples=lineparts[4:]
		words.append(word)
	return words
		
class User:
	def __init__(self,username="Sam"):
		self.name=username
		self.perdiem=100
		self.cycle=4
	
	def __str__(self):
		return self.name
	
	def __len__(self):
		return len(self.name)
	
	def dump(self,indented="\t",singleindent="\t",encoding="utf-8"):
		outstring=indented+'<User perdiem="%s" cycle="%s">%s</User>\n' % (self.perdiem,self.cycle,self.name)
		return outstring
		
	def load(self,instring=""):
		pieces=re.findall('\<User perdiem=\"(.*?)" cycle="(.*?)">(.*?)\<\/User\>',instring)
		if not pieces:
			return False
		else:
			self.name=pieces[0][2]
			self.perdiem=pieces[0][0]
			self.cycle=pieces[0][1]
			return True
		
class MetaVocab:
	def __init__(self,language="",filepath="",newwords=[],user=User(""),lastsession=0,restorefrom="D:\\statusfile.txt",dummy=False):
		self.user=user
		self.username=str(user)
		words=set(newwords)
		if filepath:
			words|=set(restore(filepath))
		self.words=list(words)
		self.allwords=set(self.words)
		if restorefrom:
			self.load(open(restorefrom).read())
		self.sessionid=time.time()
		status=(0,0,0)
		self.current_word=JaWord()
		self.current_text=""
		self.done=set()
		self.redo=set()
		self.can_assess=True
		self.direction=1

class Vocabulary(MetaVocab):
	def __init__(self,language="",filepath="",newwords=[],user=User("Sam"),lastsession=0,restorefrom="",ispractice=False):
		MetaVocab.__init__(self,language=language,filepath=filepath,newwords=newwords,user=user,lastsession=lastsession,restorefrom=restorefrom)
		words=set(newwords)
		if filepath:
			words|=set(restore(filepath))
		self.words=list(words)
		self.language=language
		self.user=user
		self.goal=1000
		self.allwords=set(self.words)
		self.is_practice= ispractice
		if restorefrom:
			self.load(open(restorefrom).read())
			self.path=restorefrom
		else:
			self.path=""
		self.sessionid=time.time()
		cap=user.cycle-(user.cycle*int(self.is_practice)) # if practice session, only 0s
		status=self.filter(thecap=cap)
		print cap,status
		try:
			self.current_word=self.words[0]
		except IndexError:
			self.current_word=JaWord()
		self.can_assess= 64000 < self.sessionid - lastsession
		self.getstats()

	def __iter__(self):
		return iter(self.words)
	
	def __len__(self):
		return len(self.words)
		
	def __str__(self):
		return str(self.current_word)
		
	def __getitem__(self,index):
			return self.words[index]
		
	def __setitem__(self,index,item):
		self.words[index]=item
		
	def index(self,item):
		return self.words.index(item)
		
	def rotate(self):
		self.done.append(self.current_word)
		index=self.words.index(self.current_word)
		ready=False
		try:
			current_word=self.words[index+1]
			ready=True
		except IndexError:
			if self.redo:
				self.words.words=list(self.redo)
				random.shuffle(self.words.words)
				self.redo=set()
				self.current_word=self.words[0]
				ready=True
		if not ready:
			return False
		else:
			return self.current_word

	def run_session(self,output="gui"):
		self.direction=1
		if output=="gui":
			run(self)
		elif output=="web":
			pass
	
	def intake(self,input=[]): #may need to do some additional validation here
		self.filter(input=input,maxnew=self.user.perdiem)
		return (len(input[:self.user.perdiem]),len(self))
	
	def filter(self,thecap=-1,maxreview=20,maxnew=20,reviewgap=600000,input=[]):
		review=0
		new=0
		if thecap == -1:
			thecap=self.user.cycle
		available=[(len(x.successes),x) for x in self.allwords if x.status==1]
		unavailable=[x for x in self.allwords if x.status < 1]
		self.words=[]
		thegroup=Group()
		available.sort()
		available.reverse() # in case of conflict, privilege more-learned over less-learned
		available=[x[1] for x in available]
		for w in available:
			if not w.gloss:
				continue
			if w.count() > self.user.cycle:
				w.status=-1
			if w.count() > thecap:
				continue
			if thegroup.ok2add(w):
				thegroup.add(w)
				self.words.append(w)
				self.allwords.add(w)
			else:
				w.status=0
		for w in unavailable:
			if w.status == 0: #sequestered
				dels=[x for x in w.history if x[0]==-100]
				if dels: # has been deleted
					continue
				seqs=[x for x in w.history if x[0] in [100,200]]
				try:
					if time.time()-seqs[-1][1] < 600000: # at least 1 week must elapse
						continue
				except IndexError:
					w.history.append((200,time.time(),self.sessionid))
					continue
			elif w.status == -1: #concluded			
				if review < maxreview and time.time()-w.successes[-1][1] > reviewgap: #keeping this very crude for now
					pass
				else:
					continue
			else:
				continue
			if thegroup.ok2add(w):
				review+=1
				thegroup.add(w)
				self.words.append(w)
				self.allwords.add(w)
				w.status=1
		if input: #new words being added
			for w in input:
				print str(w)
				if not w.gloss:
					print 1
					continue
				if new >= maxnew:
					print 2
					continue
				if thegroup.ok2add(w):
					print 3
					thegroup.add(w)
					self.words.append(w)
					self.allwords.add(w)
					new+=1
				else:
					print 4
					w.status=0
					w.history.append((200,time.time(),self.sessionid))
		random.shuffle(self.words)
		self.getstats()
		return (new,review,len(self.words),len(self.allwords))

	def dump(self,encoding="utf-8"):
		outstring='<Vocabulary language="%s" goal="%s">\n' % (str(self.language),str(self.goal))
		outstring+=self.user.dump(indented="\t")
		for w in self.allwords:
			outstring+=w.dump(encoding=encoding)
		outstring+="</Vocabulary>\n"
		return outstring
		
	def load(self,instring="",encoding="utf-8",filepath="D:\\statusfile.txt"): 
		firstline=instring.split("\n",1)[0]
		if '<Vocabulary' in firstline:
			if 'language="' in firstline:
				self.language=firstline.split('language="',1)[1].split('"')[0]
			if 'goal="' in firstline:
				self.goal=int(firstline.split('goal="',1)[1].split('"')[0])
		wordies=[x.split("</Word")[0].decode(encoding,"ignore") for x in instring.split('<Word name="')[1:]]
		print len(wordies)
		for w in wordies:
			word=JaWord()
			word.mainform=w.split('"',1)[0]
			try:
				word.status=int(w.split('status="')[1].split('"')[0])
			except IndexError:
				pass
			word.rom=w.split("<Romanization>")[1].split("</Romanization>")[0]
			word.kana=w.split("<Kana>")[1].split("</Kana>")[0]
			word.gloss=w.split("<Gloss>")[1].split("</Gloss>")[0]
			word.glossed=w.split("<Glossed>")[1].split("</Glossed>")[0]
			history=w.split("<History>")[1].split("</History>")[0]
			hist_events=[x.split("</Event>")[0] for x in history.split("<Event")[1:]]
			for h in hist_events:
				if not h.strip(): continue
				value=h.split('value="')[1].split('"',1)[0]
				session=float(h.split('session="')[1].split('"',1)[0])
				timestamp=float(h.split(">")[1].split("<")[0])
				word.history.append((value,timestamp,session))
			success=w.split("<Successes>")[1].split("</Successes>")[0]
			ss=[x.split("</Event>")[0] for x in success.split("<Event")[1:]]
			for s in ss:
				if not s.strip(): continue
				try:
					session=float(s.split('session="')[1].split('"',1)[0])
				except:
					print s
				timestamp=float(s.split(">")[1].split("<")[0])
				word.successes.append((timestamp,session))
			failure=w.split("<History>")[1].split("</History>")[0]
			ff=[x.split("</Event>")[0] for x in failure.split("<Event")[1:]]
			for f in ff:
				if not f.strip(): continue
				session=float(f.split('session="')[1].split('"',1)[0])
				timestamp=float(f.split(">")[1].split("<")[0])
				word.failures.append((timestamp,session))
			try:
				examples=[x.split("</Example>")[0].split(">",1) for x in w.split("<Example")[1:]]
				for e in examples:
					newexample=Example(e[1].strip())
					if 'href="' in e[0]:
						newexample.href=e[0].split('href="')[1].split('"')[0]
					if 'priority="' in e[0]:
						newexample.priority=int(e[0].split('priority="')[1].split('"')[0])
					word.examples.append(newexample)
			except IndexError: print "No examples: ",word.rom
			try:
				seq=w.split("<Sequestered>")[1].split("</Sequestered>")[0]
				if seq.strip().lower() in ["true","false"]:
					word.sequestered=bool(eval(seq.title()))
			except IndexError:
				pass
			self.allwords.add(word)
		self.getstats()
		return True
		
	def undo(self,index):
		word=self.words[index]
		if not word.history:
			return False
		else:
			this=word.history[-1]
			if this[0] == 1:
				word.successes=word.successes[:-1]
			word.history=word.history[:-1]
			return True
	
	def sequester(self,word):
		word.history.append((100,self.sessionid,time.time()))
		word.successes=[] #reset the counter
		word.sequestered=True
		word.status=0
		self.words.remove(word)
		
	def delete(self,word):
		if word.status==0 and word.sequestered==True and word.history and word not in self.words:
			if word.history[-1][0] == -100:
				return False # already deleted
		word.history.append((-100,self.sessionid,time.time()))
		word.sequestered=True
		word.status=0
		if word in self.words:
			print "deleting..."
			self.words.remove(word)
		if hasattr(word,"wordbox"): # replace with blankness?
			word.wordbox.SetLabel("")
			word.wordbox.SetStyle(wx.DEFAULT)
			word.glossbox.SetLabel("")
			word.longglossbox.SetLabel("")
			word.checkbox.SetValue(False)
		return True
	
	def getstats(self):
		self.actives=[x for x in self.words if x.status==1]
		incoming=[x for x in self.actives if len(x.successes) == 0]
		seqs=[x for x in self.words if x.status == 0 and x.sequestered]
		deleteds=[x for x in self.words if x.status ==0 and "-100," in str(x.history)]
		done=[x for x in self.words if x.status == -1]
		doneplus=[x for x in self.words if x.status ==-1 and len(x.successes) > self.user.cycle]
		self.active=len(self.actives)
		self.sequestered=len(seqs)
		self.deleted=len(deleteds)
		self.done=len(done)
		self.doneplus=len(doneplus)
		self.incoming=len(incoming)

	
class Group(MetaVocab):
	def __init__(self,maxsize=100,members=set(),tooclose=0.3,language="",filepath="",newwords=[],user=User(""),lastsession=0,restorefrom=""):
		MetaVocab.__init__(self,language=language,filepath=filepath,newwords=newwords,user=user,lastsession=lastsession,restorefrom=restorefrom)
		self.allwords|=members
		self.words.extend(list(members))
		self.romanizations=set([x.rom for x in self.words])
		self.glosses=set()
		self.wordcloud=set()
		self.max=maxsize
		self.tooclose=tooclose # minimum edit distance between members as divided by word length
		self.storage=set()
		
	def glom(self,argument=[]):
		if not argument:
			argument=[x.mainform for x in self.words]
		glomstring=" ".join(list(argument))
		return glomstring
	
	def ok2add(self,word,definition="",proceed=False,biglist=[],maxoverlap=1,worry_about_length=False):
		if len(self.words) >= self.max and worry_about_length:
			return False
		if not definition:
			definition=word.glossed
		stringword=word.mainform
		romword=word.rom
		if stringword in self.glom(): #in case there is already a longer word/phrase containing this
			return False
		if romword in self.glom(self.romanizations):
			return False
		closes=[y for y in [(x,romword,2.0*distance(x,romword)/len(romword+x)) for x in self.romanizations] if y[2] < self.tooclose]
		if closes:
			print str(closes)
			return False
		elif definition and maxoverlap:
			if definition in self.glom(self.glosses):
				return False
			else:
				cloud=wordcloud(definition)
				if len(cloud.intersection(self.wordcloud)) >= maxoverlap:
					return False
		return True

	def add(self,word,definition="",tupled=False):
		self.words.append(word)
		random.shuffle(self.words)
		self.allwords.add(word)
		self.glosses.add(definition)
		self.wordcloud|=wordcloud(definition)
		if tupled:
			self.storage.add(tupled)

class ManagerWindow(wx.Frame):
	def __init__(self,words=Vocabulary(),user=User("Sam"),language="Japanese",direction=1):
		wx.Frame.__init__(self, None, wx.ID_ANY, "Vocabulary Manager for %s, learning %s" % (str(user),language),size=wx.Size(600,500))
		self.tabs=wx.Notebook(self, -1,wx.Point(0,0), wx.Size(0,0), style=wx.NB_FIXEDWIDTH|wx.NB_RIGHT)
		self.words=words
		self.color = wx.SystemSettings.GetColour(wx.SYS_COLOUR_BTNFACE)
		self.username=str(user)
		self.user=user
		self.language=language
		self.direction=direction
		self.loadsource="D:\\japa.txt"
		self.currentdir=os.getcwd()
		print self.currentdir
		self.panel = wx.Panel(self.tabs, wx.ID_ANY)
		self.panel2 = wx.Panel(self.tabs, wx.ID_ANY)
#		self.panel3 = wx.Panel(self.tabs, wx.ID_ANY, style=wx.VSCROLL)
		self.panel3=wx.lib.scrolledpanel.ScrolledPanel(self.tabs, wx.ID_ANY, size=(500, 6000), style=wx.TAB_TRAVERSAL)
		self.panel4 = wx.Panel(self.tabs, wx.ID_ANY)
		self.panel5 = wx.Panel(self.tabs, wx.ID_ANY)
		self.tabs.AddPage(self.panel,"Main")
		self.tabs.AddPage(self.panel2,"Pie")
		self.tabs.AddPage(self.panel3,"Edit")
		self.tabs.AddPage(self.panel4,"Settings")
		self.tabs.AddPage(self.panel5,"Texts")
		self.labelstring="You are currently learning %s words of %s.  You have an estimated %s vocabulary, including words in all stages of learning, of %s words." 
		self.atext = wx.StaticText(self.panel, label=self.labelstring % (str(len(self.words)),self.language,self.language,str(len(self.words.allwords))),style=wx.EXPAND|wx.TE_MULTILINE|wx.TE_LINEWRAP,size=wx.Size(200,200))
		self.loadbutton=wx.Button(self.panel,id=wx.ID_ANY,label="&Load %s new words" % str(self.words.user.perdiem),name="load")
		if not self.words.can_assess:
			self.loadbutton.Disable()
		gobutton=wx.Button(self.panel, id=wx.ID_ANY, label="&Test your knowledge", name="start")
		self.practicebutton=wx.Button(self.panel, id=wx.ID_ANY, label="&Review %s new/restarted words" % str(self.words.incoming), name="practice")
		gobutton.Bind(wx.EVT_BUTTON, self.onButton)
		self.loadbutton.Bind(wx.EVT_BUTTON,self.onButton)
		self.practicebutton.Bind(wx.EVT_BUTTON,self.onButton)
		self.filer= wx.TextCtrl(self.panel, value=self.words.path,size=wx.Size(150,30),style=wx.EXPAND)
		self.filelabel="Set your vocabulary here. "
		filebutton=wx.Button(self.panel, id=wx.ID_ANY, label="Select &file ", name="file")
		filebutton.Bind(wx.EVT_BUTTON,self.onButton)
		self.filebefore = wx.StaticText(self.panel, label=self.filelabel)
		topsizer=wx.BoxSizer(wx.HORIZONTAL)
		sizer=wx.BoxSizer(wx.VERTICAL)
		topsizer.Add(self.atext,0)
		topsizer.Add((20,20),0)
#		topsizer.Add(self.pie,0)
		sizer.Add(topsizer)
		sizer.Add(self.practicebutton,0)
		sizer.Add((0,0), 1) 
		hsizer=wx.BoxSizer(wx.HORIZONTAL)
		hsizer.Add(gobutton,1)
		hsizer.Add(self.loadbutton,1)
		sizer.Add(hsizer)
		sizer.Add((0,0), 1) 
		sizer.Add(self.filebefore,0)
		filesizer=wx.BoxSizer(wx.HORIZONTAL)
		filesizer.Add(self.filer)
		filesizer.Add(filebutton)
		sizer.Add(filesizer)
		self.panel.SetSizer(sizer)
		if not self.words:
			if "statusfile.txt" in os.listdir(self.currentdir):
				self.loadFile(os.path.join(self.currentdir,"statusfile.txt"))
		if not self.words:
			self.buildEditor()
		self.drawPie()

	def drawPie(self):
		self.pie=wx.lib.agw.piectrl.PieCtrl(self.panel2, size=wx.Size(300,270))
		self.pie.SetHeight(50)
		part = wx.lib.agw.piectrl.PiePart()
		part.SetLabel("Words to learn: %s" % str(self.words.goal))
		part.SetValue(100)
		part.SetColour(wx.Colour(200, 50, 50))
		self.pie._series.append(part)
		part2 = wx.lib.agw.piectrl.PiePart()
		part2.SetLabel("Words learned: %s" % self.words.done) 
		part2.SetValue(100.0*self.words.done/self.words.goal)
		part2.SetColour(wx.Colour(50,200,200))
		self.pie._series.append(part2)
		part3 = wx.lib.agw.piectrl.PiePart()
		part3.SetLabel("Words in progress: %s" % self.words.active) 
		part3.SetValue(100.0*self.words.active/self.words.goal)
		part3.SetColour(wx.Colour(50,200,50))
		self.pie._series.append(part3)
		self.pie.SetBackColour(self.color)
		legend=self.pie.GetLegend()
		legend.SetTransparent(True)

	def buildEditor(self,isagain=False):
		if not self.words:
			return False
		vsizer=wx.BoxSizer(wx.VERTICAL)
		panel=self.panel3
		applybutton=wx.Button(panel, id=wx.ID_ANY, label="Apply and &save", name="apply",style=wx.EXPAND)
		saveasbutton=wx.Button(panel, id=wx.ID_ANY, label="Apply and Save &As", name="saveas",style=wx.EXPAND)
		cancelbutton=wx.Button(panel, id=wx.ID_ANY, label="&Cancel changes", name="cancel",style=wx.EXPAND)
		applybutton.Bind(wx.EVT_BUTTON, self.applyChanges)
		cancelbutton.Bind(wx.EVT_BUTTON, self.applyChanges)
		saveasbutton.Bind(wx.EVT_BUTTON, self.applyChanges)
		buttonsizer=wx.BoxSizer(wx.VERTICAL)
		buttonsizer.Add(applybutton)
		buttonsizer.Add((20,20), 1) 		
		buttonsizer.Add(cancelbutton)
		buttonsizer.Add((20,20), 1)
		buttonsizer.Add(saveasbutton)
		vsizer.Add(buttonsizer)
		vsizer.Add((5,5),1)
		print len(self.words.words),len(self.words.allwords)
		for word in self.words.words:
			if not hasattr(word,"wordbox"):
				word.wordsizer=wx.BoxSizer(wx.HORIZONTAL)
				word.wordbox=wx.TextCtrl(panel, value=word.mainform,size=wx.Size(150,20),style=wx.TE_READONLY)
				word.glossbox=wx.TextCtrl(panel, value=word.gloss,size=wx.Size(100,20))
				word.longglossbox=wx.TextCtrl(panel, value=word.glossed,size=wx.Size(200,20))
				word.checkbox=wx.CheckBox(panel,0,"Delete")
				word.wordsizer.Add(word.wordbox,1)
				word.wordsizer.Add(word.glossbox,1)
				word.wordsizer2=wx.BoxSizer(wx.HORIZONTAL)
				vsizer.Add(word.wordsizer)
				word.wordsizer2.Add(word.longglossbox)
				word.wordsizer2.Add(word.checkbox)
				vsizer.Add(word.wordsizer2)
				vsizer.Add((5,5),1)
			else:
				word.wordbox.SetLabel(word.mainform)
				word.glossbox.SetLabel(word.gloss)
				word.longglossbox.SetLabel(word.glossed)
				word.checkbox.SetValue(False)
		vsizer.Layout()
		panel.SetSizer(vsizer)
		panel.Bind(wx.EVT_SET_FOCUS,self.onFocusEditor)
		if not isagain:
			panel.SetupScrolling()
		return True

	def onFocusEditor(self,event):
		self.panel3.SetFocus()

	def applyChanges(self,event):
		button = event.GetEventObject()
		response=button.GetName()[:1]
		print response,response
		if response == "a" or response == "s":
			for word in list(self.words.words):
				if word.wordbox.GetValue().strip() != word.mainform.strip(): # a new word has been entered
					if word.checkbox.GetValue():
						continue
					else:
						newword=JaWord()
						newword.mainform=word.wordbox.GetValue().strip()
						newword.gloss=word.glossbox.GetValue.strip()
						newword.glossed=word.longglossbox.GetValue().strip()
						self.words.words.append(newword)
						self.words.allwords.add(newword)
						self.words.getstats()
						self.refreshtopline()
						print word.rom,word.mainform
				if word.checkbox.GetValue():
					self.words.delete(word)
					print word.rom,"d"
				if word.glossbox.GetValue().strip() != word.gloss.strip():
					word.gloss=word.glossbox.GetValue().strip()
					print word.rom,word.gloss
				if word.longglossbox.GetValue().strip() != word.glossed.strip():
					word.glossed=word.longglossbox.GetValue().strip()
					print word.rom,word.glossed
			if self.words.path and not response == "s":
				print 1
				writefile=open(self.words.path,"w")
				with writefile:
					writefile.write(self.words.dump())
			else:
				print 2
				self.saveFile()
		self.buildEditor(True)
		
	def onButton(self,event):
		button = event.GetEventObject()
		response=button.GetName()[:1]
		print response
		if response == "s":
			self.form=CardForm(parent=self,words=self.words,username=self.username,language=self.language,direction=self.direction)
			self.form.Show()
		elif response == "l":
			wordsin=restore(self.loadsource)
			foo=self.words.intake(wordsin)
			self.refreshtopline()
			print foo
		elif response == "p":
			self.words.is_practice=True
			status=self.words.filter(thecap=0)
			print status
			self.form=CardForm(parent=self,words=self.words,username=self.username,language=self.language,direction=self.direction)
			self.form.Show()
		elif response=="f":
			dialog = wx.FileDialog (self.panel, message = 'Open vocabulary file', wildcard = "Text files (*.txt)|*.txt", style = wx.OPEN )
			if dialog.ShowModal() == wx.ID_OK:
				selected = dialog.GetPath()
				self.loadFile(selected)
			dialog.Destroy()			

	def loadFile(self,selected):
		self.filer.SetLabel("")
		self.filer.AppendText(selected)
		try:
			newwords=Vocabulary(restorefrom=selected)
			if newwords:
				self.filebefore.SetLabel("Loaded vocabulary.")
				self.words=newwords
				self.words.path=selected
				self.refreshtopline()
			else:
				self.filebefore.SetLabel("Unable to load.")
				self.refreshtopline()
		except:
			self.filelabel="Invalid file."
			self.filebefore.SetLabel(self.filelabel)
			self.refreshtopline()
			
	def saveFile(self):
		directory=os.getcwd()
		dialog = wx.FileDialog (self.panel, message = 'Save vocabulary file', wildcard = "Text files (*.txt)|*.txt", style = wx.SAVE | wx.FD_OVERWRITE_PROMPT | wx.FD_CHANGE_DIR )
		outcome=dialog.ShowModal()
		if outcome == wx.ID_OK:
				selected = dialog.GetPath()
				print selected
				self.words.path=selected
				output=self.words.dump()
				outfile=open(selected,"w")
				with outfile:
					outfile.write(output)
		else:
			pass
		dialog.Destroy()			
		

	def refreshtopline(self):
		self.atext = wx.StaticText(self.panel, label=self.labelstring % (str(len(self.words)),self.language,self.language,str(len(self.words.allwords))),style=wx.EXPAND|wx.TE_MULTILINE|wx.TE_LINEWRAP,size=wx.Size(200,200))
		self.practicebutton.SetLabel("&Review %s new/restarted words" % str(self.words.incoming))
		self.buildEditor()
		self.drawPie()
				
				
class CardForm(wx.Frame):
	def __init__(self,parent=None,words=Vocabulary(),username="Sam",language="Japanese",direction=1):
		titlestring="Flashcards for %s, learning %s" % (username,language)
		if words.is_practice:
				titlestring+=" (Practice Session)"
		wx.Frame.__init__(self, parent, wx.ID_ANY, titlestring,size=wx.Size(600,600))
		self.input=words
		self.sessiondirection=direction
		self.direction=direction # 1 = forward, -1=back -- direction of card, not necessarily of session
		self.shown=0 # start with details hidden
		self.nulldict=dict([(x,"") for x in words])
		if type(words[0]) == tuple:
			self.words=[x[0] for x in words]
			self.examples=dict([(x[0],x[1][0]) for x in words])
			self.examples2=dict([(x[0],"\n".join(x[1][1:])) for x in words])
		elif hasattr(words[0],"mainform"):
			self.words=words
			self.examples=dict([(x,x.kana) for x in words])
			self.examples2=dict([(x,u"\r\n".join([y.text for y in x.examples])) for x in words])			
		else:
			self.words=words
			self.examples=self.nulldict
			self.examples2=self.nulldict
		self.words2=self.words.words #store a copy
		random.shuffle(self.words.words)
		self.current_word=self.words[0]
		if self.sessiondirection == 1:
			self.current_text=self.current_word.mainform
		elif self.sessiondirection == -1:
			self.current_text=self.current_word.gloss
		self.panel = wx.Panel(self, wx.ID_ANY)
		wordfont=wx.Font(35,wx.DEFAULT,wx.NORMAL,wx.NORMAL)
		examplefont=wx.Font(15,wx.DEFAULT,wx.NORMAL,wx.NORMAL)
		color = wx.SystemSettings.GetColour(wx.SYS_COLOUR_BTNFACE)
		self.color=color
		self.atext = wx.TextCtrl(self.panel, value=self.current_text,style=wx.EXPAND|wx.TE_READONLY|wx.ALIGN_CENTER|wx.BORDER_NONE|wx.TE_MULTILINE|wx.TE_NO_VSCROLL,size=wx.Size(300,75))
		self.atext.SetLabel(self.current_text)
		self.atext.SetBackgroundColour(color)
		self.atext.SetFont(wordfont)
		self.btext = wx.TextCtrl(self.panel, value="",style=wx.EXPAND|wx.TE_READONLY|wx.ALIGN_CENTER|wx.TE_MULTILINE|wx.BORDER_NONE|wx.TE_NO_VSCROLL,size=wx.Size(300,50))
		self.btext.SetLabel("")
		self.btext.SetFont(examplefont)
		print self.examples[self.current_word]
		self.btext.SetBackgroundColour(color)
#		self.ctext = wx.StaticText(self.panel, label=self.examples2[self.current_word],style=wx.EXPAND,size=wx.Size(200,250))
		self.ctext = wx.TextCtrl(self.panel, value="",style=wx.EXPAND|wx.TE_READONLY|wx.BORDER_NONE|wx.TE_NO_VSCROLL|wx.TE_MULTILINE,size=wx.Size(300,250))
		self.ctext.SetLabel("")
		self.ctext.SetBackgroundColour(color)
		self.ctext.SetFont(examplefont)
		self.ctext.HideNativeCaret()
		sizer = wx.BoxSizer(wx.VERTICAL)
		hsizer=wx.BoxSizer(wx.HORIZONTAL)
		row1=wx.BoxSizer(wx.HORIZONTAL)
		row2=wx.BoxSizer(wx.HORIZONTAL)
		row3=wx.BoxSizer(wx.HORIZONTAL)
		column=wx.BoxSizer(wx.VERTICAL)
		sizer.Add(self.atext,0)
		sizer.Add(self.btext,0)
		self.ybutton = wx.Button(self.panel, id=wx.ID_ANY, label="Yes", name="yes")
		self.nbutton = wx.Button(self.panel, id=wx.ID_ANY, label="No", name="no")
		self.sbutton = wx.Button(self.panel, id=wx.ID_ANY, label="Skip -- try later", name="skip")
		self.qbutton = wx.Button(self.panel, id=wx.ID_ANY, label="End this session, save results", name="quit")
		self.obutton = wx.Button(self.panel, id=wx.ID_ANY, label="Oops-- incorrectly marked previous", name="oops")
		self.fbutton = wx.Button(self.panel, id=wx.ID_ANY, label="Flip card", name="flip")
		self.dbutton = wx.Button(self.panel, id=wx.ID_ANY, label="Show/hide details", name="details")
		self.rbutton = wx.Button(self.panel, id=wx.ID_ANY, label="Remove this card, too confusing", name="remove")
		buttons1 = [self.ybutton, self.nbutton]
		buttons2 = [self.dbutton,self.fbutton]
		buttons3=  [self.qbutton,]
		buttons4= [self.sbutton,self.obutton,self.rbutton]
		for button in buttons1:
			self.buildButtons(button, row1)
		for button in buttons2:
			self.buildButtons(button,row2)
		for button in buttons3:
			self.buildButtons(button,row3)
		for button in buttons4:
			self.buildButtons(button,column)
		sizer.Add(row1)
		sizer.Add(row2)
		if self.ctext:
			sizer.Add(self.ctext,0)
		sizer.Add(row3)
		hsizer.Add(sizer)
		hsizer.Add(column)
		self.panel.SetSizer(hsizer)
		self.dbutton.SetFocus()

	def buildButtons(self, btn, sizer):
		btn.Bind(wx.EVT_BUTTON, self.onButton)
		sizer.Add(btn, 0, wx.ALL, 5)

	def onButton(self, event):
		button = event.GetEventObject()
		response=button.GetName()[:1]
		if response == "y":
			self.current_word.succeed(self.words.sessionid,self.words.is_practice)
			self.shown=0
		elif response == "n":
			self.current_word.fail(self.words.sessionid)
			if self.words.is_practice:
				self.words.redo.add(self.current_word)
			self.shown=0
		elif response == "s":#skip
			self.current_word.skip(self.words.sessionid)
			self.words.redo.add(self.current_word)
			self.shown=0
		elif response == "o": # oops
			if self.words.index(self.current_word) > 0: 
				self.words.undo(self.words.index[self.current_word]-1)
		elif response == "q": # quit and save
			self.closeout()
			return
		elif response == "f": #flip
			self.flip()
			self.nbutton.SetFocus()
			return
		elif response == "d": #details toggle
			self.showhide()
			self.nbutton.SetFocus()
			return
		elif response == "r": #remove
			index=self.words.index(self.current_word)
			self.words.sequester(self.current_word)
			try:
				self.current_word=self.words[index]
				self.direction=self.sessiondirection
				self.update()
				return
			except:
				self.onend()
				return
		time.sleep(0.25)
		try:
			self.current_word=self.words[self.words.index(self.current_word)+1]
			if self.sessiondirection == 1:
				self.current_text=self.current_word.mainform
			elif self.sessiondirection == -1:
				self.current_text=self.current_word.gloss
		except IndexError:
			self.onend()
		self.direction=self.sessiondirection
		self.update()
		print self.current_text,response
		
	def update(self): #update displays for new word
		if self.sessiondirection == 1:
			self.current_text=self.current_word.mainform
		elif self.sessiondirection == -1:
			self.current_text=self.current_word.gloss
		self.atext.SetLabel(self.current_text)
		if self.shown:
			self.ctext.SetLabel(self.examples2[self.current_word])
			if self.sessiondirection == 1:
				self.btext.SetLabel(self.examples[self.current_word])
			else:
				self.btext.SetLabel(self.current_word.glossed)
		else:
			self.btext.SetLabel("")
			self.ctext.SetLabel("")

	def onend(self):
		print "End of set"
		if self.words.redo:
			self.words.words=list(self.words.redo)
			random.shuffle(self.words.words)
			print "Redo: "+str(len(self.words.words))
			self.words.redo=set()
			self.current_word=self.words[0]
			self.update()
		elif self.sessiondirection == -1: 
			self.closeout()
		else: # reverse course
			self.words.words=self.words2 
			self.sessiondirection=-1
			self.direction=-1
			random.shuffle(self.words.words)
			self.current_word=self.words[0]
			self.current_text=self.words[0].gloss
			self.examples=self.nulldict
			self.examples2=self.nulldict

	def closeout(self):
			dump=self.input.dump()
			file=open("D:\\statusfile.txt","w")				
			with file:
				file.write(dump)
			self.Destroy()
			print type(self.words)

	def flip(self):
		if self.sessiondirection == 1:
			if self.direction==1:
				self.atext.SetLabel(self.current_word.gloss)
				self.ctext.SetLabel("")
				if self.shown:
					self.btext.SetLabel(self.current_word.glossed) #long-form defn
				else:
					self.btext.SetLabel("")
			elif self.direction==-1:
				self.atext.SetLabel(self.current_word.mainform)
				if self.shown:
					self.btext.SetLabel(self.examples[self.current_word]) #long-form defn
					self.ctext.SetLabel(self.examples2[self.current_word])
				else:
					self.btext.SetLabel("")
					self.ctext.SetLabel("")
		elif self.sessiondirection == -1:
			if self.direction==1:
				self.atext.SetLabel(self.current_word.gloss)
				if self.shown:
					self.btext.SetLabel(self.current_word.glossed) #long-form defn
				else:
					self.btext.SetLabel("")
			elif self.direction==-1:
				self.atext.SetLabel(self.current_word.mainform)
				if self.shown:
					self.btext.SetLabel(self.examples[self.current_word]) #long-form defn
					self.ctext.SetLabel(self.examples2[self.current_word])
				else:
					self.btext.SetLabel("")
					self.ctext.SetLabel("")
		self.direction=0-self.direction

	def showhide(self):
			print self.shown
			self.shown=list(set([0,1])-set([self.shown]))[0]
			if self.shown==0:
				self.btext.SetLabel("")
				self.ctext.SetLabel("")
			elif self.direction==1:
				self.btext.SetLabel(self.examples[self.current_word])
				self.ctext.SetLabel(self.examples2[self.current_word])
			elif self.direction==-1:
				self.btext.SetLabel(self.current_word.glossed)
				self.ctext.SetLabel("")
			print self.shown

class LevelTest:
	def __init__(self):
		self.done=set()
		self.wordlist=[]
		self.bandwidth=500
		self.chunksize=50
		
	def go(self,thelist=[]):
		if not thelist:
			thelist=self.wordlist
			if not thelist:
				return False
		prepped=self.prepleveltest(thelist)
		result=self.dynamic_ez(prepped)
		resultupled=[(x,result[x]) for x in result.keys()] # avoid annoyances of randomosity
		resultupled.sort()
		return resultupled 
	
	def prepleveltest(bigwordlist=[]): # must be sorted list of strings or word objects or (freq,string) tuples, from most to least frequent
		bands=[]
		self.wordlist=list(bigwordlist)
		while bigwordlist:
			bands.append(set(bigwordlist[:self.bandwidth]))
			bigwordlist=bigwordlist[self.bandwidth:]
		output=[(self.bandwidth*bands.index(x),random.sample(x,self.chunksize)) for x in bands]
		return output
		
	def leveltest_ez(input=[(0,set())]):
		pass
		
	def leveltest_mc(input=[(0,set())]):
		pass

	def dynamic_ez(input=[(0,[""])]):
		app=wx.App(False)
		outcome={}
		previous=False
		for b in input:
			banded=bandtest_ez(b[1])
			if type(banded) == tuple and banded[0] == False:
				print "Cancelled"
				return outcome
			outcome[b[0]]=10.0*banded
			print b[0],outcome[b[0]]
			if previous:
				loopcheck=0
				while outcome[previous[0]] - outcome[b[0]] < -15.0: # going backwards? should normally be positive, but allowing down to -15 to avoid excess looping
					loopcheck+=1
					if loopcheck > 3: break
					try:
						newprev=10*bandtest_ez(previous[1])
						outcome[previous[0]]=0.5*(outcome[previous[0]]+newprev)
						newthis=10*bandtest_ez(b[1])
						outcome[b[0]]=0.5*(outcome[b[0]]+newthis)
					except TypeError: #cancelled
						print "Cancelled"
						return outcome
			if outcome[b[0]] < 25.0: # are we past the point of diminishing returns?
				break
			previous=b
		return outcome
		
	def bandtest_ez(wordset):
		if type(list(wordset)[0]) == tuple:
			wordset=set([x[1] for x in list(wordset)])
		wordset=[str(x) for x in wordset]
		thelist=list(wordset)
		random.shuffle(thelist)
		chunks=[]
		thescore=0.0*10
	#	tally=(0,0)
	#	print str(len(c)),str(tally)
		yes=0
		c=thelist[:5]
		for word in c:
			card=wx.MessageDialog(None, str(word), "Do you know this word?",wx.YES_NO |wx.CANCEL|wx.NO_DEFAULT )
			response=card.ShowModal()
			if response == wx.ID_YES:
				yes+=1
			elif response == wx.ID_CANCEL:
				return (False,thescore)
			card.Destroy()
	#	newscore=10.0*(tally[0]+yes)/(tally[1]+len(c))
		newscore=10.0*yes/5
	#	if int(newscore) == int(thescore) or abs(newscore-thescore) < 1.0:
	#		print newscore,thescore,"yes"
	#		return newscore
	#	else:
	#		print newscore,thescore
	#		tally=(tally[0]+yes,tally[1]+len(c))
	#		thescore=newscore
	#	if yes==5 or yes ==0: # not necessary to test further
	#		break
		return newscore

		
		
def cliptext():
	if not wx.TheClipboard.IsOpened():
		wx.TheClipboard.Open()
		texty = wx.TextDataObject()
		result= wx.TheClipboard.GetData(texty)
		if result:
			return texty.GetText()
		wx.TheClipboard.Close()
	else:
		return ""

def run(words):
	app=wx.App(False)
	form=ManagerWindow(words=words)
	form.Show()
	app.MainLoop()
	del(app)
	
	
def run2(plus=False,filepath="D:\\japa.txt"):
	import japa
	reload(japa)
	words=japa.restore(filepath)
	if not plus:
		forms=[x.mainform for x in words]
	else:
		forms=[(x.mainform,[x.kana]+x.examples) for x in words]
	run(forms)

def run3():
	foo=Vocabulary()
	foo.run_session()
	
if __name__ == "__main__" :
	run3()

ext()
		wx.TheClipboard.Close()
	else:
		return ""

def run(words):
	app=wx.App(False)
	form=ManagerWindow(words=words)
	form.Show()
	app.MainLoop()
	del(a
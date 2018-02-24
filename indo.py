import os,re
import datetime, time
import urllib2,cookielib
from htmlentitydefs import name2codepoint
from random import choice
from string import punctuation

from nltk.metrics import edit_distance as distance
from nltk.corpus import stopwords
from nltk.corpus import wordnet as wn

dir="C:\Indo"
kdir="C:\Corp\Kompas"
readingdir="C:\Indo\Reading"

wordmatcher='(?<=\W)[a-z][a-z\-]+[a-z](?=\W)'
stops=set(stopwords.words("english"))


class Goer:
	def go(self,started=False,limit=0,filestop=False,finish=False,listonly=False,define=False,samples=2,groupsize=100,groupem=False,listplus=False,blacklist=[]):
		if not blacklist:
			blacklist=get_blacklist()
		self.wordlist={}
		defined={}
		y=0
		if started is False:
			for d in os.walk(kdir):
				if filestop:
					if y > filestop: break
				print d[0],len(d[2])
				if "agg.txt" in d[2]:
					found=re.findall(wordmatcher,open(os.path.join(d[0],"agg.txt")).read())
					for f in found:
						st=stem(f)
						if st in blacklist: continue
						try: self.wordlist[st]+=1
						except KeyError: self.wordlist[st]=1
					continue
				for f in d[2]:
					if filestop:
						y+=1
						if y > filestop:
							break
					if not f.endswith(".html"): continue
					page=open(os.path.join(d[0],f)).read()
					uniques=set(get_words(page))-blacklist
					if not uniques:
						continue
					for u in uniques:
						st=stem(u)
						if st in blacklist: continue
						try: self.wordlist[st]+=1
						except KeyError: self.wordlist[st]=1
			sorted=[(self.wordlist[x],x) for x in self.wordlist.keys()]
			sorted.sort() 
			sorted.reverse()
			self.sorted=sorted
			self.words=[x[1] for x in sorted[:limit]]
		else:
			self.words=started
		if limit != 0:
			try: 
				self.words=self.words[:limit]
			except IndexError: 
				pass
		if define and not listonly:
			self.defined=definewords(self.words)
		if listplus:
			return self.sorted
		elif listonly:
			return self.words
		self.examples=get_examples(self.words,samples,filestop)
		if groupem:
			if self.defined:
				self.groupings=sortem(self.defined,groupsize)
			else:
				self.groupings=sortem(self.words,groupsize)
			self.words=[]
			for g in self.groupings:
				self.words.extend(g.members)
		if finish:
			polish(self.words,self.examples,self.defined)
		if define:
			return (self.words,self.examples, self.defined)
		else:
			return (self.words,self.examples)

	def get_examples(self,words,count=10,filestop=False):
		self.samples=dict([(x,[(100,"")]) for x in words])
		y=0
		known=get_blacklist(exclude=["blacklist.txt"])
		for d in os.walk(kdir):
			print d[0]
			if "agg.txt" in d[2]:
				text=open(os.path.join(d[0],"agg.txt")).read()
			else:
				text=""
				for f in d[2]:
					if filestop:
						y+=1
						if y > filestop: return samples
					f=os.path.join(d[0],f)
					print f
					newtext=open(f).read()
					try: 
						newtext=newtext.split('="article_body">')[1].split("</div>",1)[0]
					except IndexError: continue
					newtext=re.sub("\<.*?\>","",newtext)
					text+=unescape(newtext)
			text+=" Z"
			for w in [x for x in words if re.search("\W"+re.escape(x)+"\W",text)]:
				newsamples=re.findall("([A-Z][^\.\?\!]+?\W"+w+"(\W[^\.\?\!]+?[\.\?\!]\s+(?=[^a-z])|[\.\?\!]\s+(?=[^a-z])))",text)
				if not newsamples: continue
				new2=[x[0].strip() for x in newsamples]
				new3=[(get_score(x,words,known),x) for x in new2]
				new3=[x for x in new3 if x[0] > 0]
				if not new3: continue
				self.samples[w].extend(new3)
				self.samples[w]=list(set(samples[w])) # eliminate duplicates
				self.samples[w].sort()
				if len(self.samples[w]) > count: self.samples[w]=self.samples[w][:count]
		return self.samples

def polish(words,examples,defined={}):
		outstring="\n"
		for w in words:
			if defined:
				if type(examples[w]) == str:
					outstring+="%s\t%s\t%s\n" % (w,defined[w],examples[w])
				else:
					outstring+="%s\t%s\t%s\n" % (w,defined[w]," | ".join([x[1] for x in examples[w]]))
			else:
				outstring+="%s\t\t%s\n" % (w.encode("utf-8","ignore"),examples[w][1].encode("utf-8","ignore"))
		file=open(os.path.join(dir,datetime.date.today().isoformat()+".txt"),"w")
		file.write(outstring)
		file.close()

def definewords(words):
		defined={}
		for w in words:
			print w
			definition=kamus(w)
			time.sleep(3)
			if not definition: 
				defined[w]=""
			else: 
				defined[w]=", ".join(definition)
		return defined
		
def kamus(word):
	url="http://www.kamus.net/result.php?w=id-indonesia&q=%s&submit=Search&e=0" % word
	try:
		page=urllib2.urlopen(url,timeout=15).read()
	except urllib2.URLError:
		try:
			page=urllib2.urlopen(url,timeout=15).read()
		except:
			return False
	if "<li>" not in page: 
		return False
	else:
		defs=page.split("<li>")[1:]
		defs=[x.split("</")[0].strip() for x in defs]
		defs=[x for x in defs if x and "<" not in x]
		return defs

def get_files(dir=kdir,suffix=".html",filestop=False): #Returns list of complete filepaths to all eligible files
	files=[]
	for d in os.walk(dir):
		print d[0]
		files.extend([os.path.join(d[0],x) for x in d[2] if x.endswith(suffix)])
		if filestop:
			if len(files) > filestop:
				break
	return files

def get_blacklist(dir=dir,exclude=[]):
	blacklist=[]
	print exclude
	for file in os.listdir(dir):
		if file in exclude: continue
		print file
		try: 
			blacklist.extend([x.split("\t")[0].strip() for x in open(os.path.join(dir,file)).read().split("\n")])
		except IOError:
			continue
	return set(blacklist)

def get_words(text,returntext=False):
	try: 
		text=text.split('="article_body">')[1].split("</div>",1)[0]
		text=unescape(text)
	except IndexError:
		if returntext: return ""
		else: return []
	text=re.sub("\<style[\s\S]+?\<\/style\>"," ",text)
	text=re.sub("\<script[\s\S]+?\<\/script\>"," ",text)
	text=re.sub("\<\!\-\-[\s\S]+?\-\-\>"," ",text)
	text=" "+re.sub("\<.*?\>","",text)+" "
	if returntext:
		return text
	else:
		words=re.findall(wordmatcher,text)
		return words

		

def aggregate(directory=kdir):
	for o in os.walk(directory):
		text=""
		print o[0]
		for file in o[2]:
			newtext=get_words(open(os.path.join(o[0],file)).read(),True)
			try: text+=newtext
			except TypeError: 
				print str(newtext)
		if not text: continue
		else:
			writefile=open(os.path.join(o[0],"agg.txt"),"w")
			with writefile:
				writefile.write(text.encode("utf-8","ignore"))
			

def get_score(sentence,learnwords=[],known=[]): #lower is better
	from string import punctuation
	wordies=[x.strip(punctuation) for x in sentence.split(" ")]
	wordies=[x.strip() for x in wordies if x.strip()]
	if len(wordies) < 3 or len(wordies) > 8: return 0
	score=len(wordies)*2
	score-=1.8*len([x for x in wordies if x.lower() in known])
	score-=len([x for x in wordies if x.lower() in learnwords])
	score+=sum([len(x)-5 for x in wordies if len(x) > 5])
	score+=sentence.count(",")+sentence.count(";")
	score+=0.5*len(re.findall('\d+',sentence))
	score+=len(re.findall('[A-Z]',sentence))
	return score

def kompas(date=datetime.date.today(),saveindex=False):
	directory=os.path.join(kdir,"Kompas_"+date.isoformat())
	try: os.mkdir(directory)
	except: pass
	firsturl="http://www1.kompas.com/index.php/newsindex/changepage/%s/%s/0/500" % (date,date+datetime.timedelta(1))
	try: 
		firstpage=urllib2.urlopen(firsturl,timeout=15).read()
	except:
		print "Failed to open "+firsturl
		return False
	urls=[x.split('"')[0] for x in firstpage.split('href="')[1:] if ".kompas.com" in x]
	print len(urls)
	if saveindex:
		file=open(os.path.join(directory,"index.html"),"w")
		file.write(firstpage)
		file.close()
	for u in urls:
		filename=u.split("/")[-1].strip()+".html"
		if filename in os.listdir(directory):
#			print filename
			continue
		print u
		try: page=urllib2.urlopen(u,timeout=15).read()
		except urllib2.URLError: 
			print "Failed!"
			continue
		page = re.sub('class=\"isi\_berita.*?\>','class="article_body">',page)
		if "article_body" not in page:
			print "Bad response."
			continue
		file=open(os.path.join(directory,filename),"w")
		file.write(page)
		file.close()
	return directory

def stem(word): #only  for stemming, not for removing meaning-added affixes
	oldword=word
	prefixes=["di"]
	suffixes=["nya","lah"]
	for p in prefixes:
		if word.startswith(p) and word != p:
			word=word[len(p):]
	for s in suffixes:
		if word.endswith(s) and word != s:
			word=word[:-len(s)]
	if len(word) < 4: return oldword
	else: return word

def get_simple(files=False,limit=10,filestop=False,finish=False,known=set()): #Find files with greatest proportion of known words
	if not known:
		known=get_blacklist(exclude=["blacklist.txt"])
	if not files:
		files=get_files(filestop=filestop)
	eligibles=[] # list of tuples
	y=0
	domains=[]
	for f in files:
		if filestop:
			y+=1
			if y > filestop:
				break
		text=open(f).read()
		try:
			domain=text.split("url=http://")[1].split(".kompas.com",1)[0]
			if domain.lower() == "english": continue
		except IndexError:
			try:
				domain=text.split("MM_openBrWindow('")[1].split(".kompas.com",1)[0]
			except IndexError:
				print "No print link or Digg for "+f
				domain=""
		try: 
			text=text.split('="article_body">')[1].split("</div>",1)[0]
			text=unescape(text)
			text=re.sub("\<.*?\>","",text)
		except IndexError:
			print "No text in "+f
			continue
		regulars=re.findall("(?<=\W)[a-z]+(?=\W)",text)
		if not regulars: 
			print "no words in "+f
			continue
		regcount=len(regulars)
		if len(regulars) < 50: 
			print "not enough words in "+f
			continue
		unknown_count=1+len([x for x in regulars if stem(x) not in known])
		score=int(regcount/unknown_count)
		eligibles.append((score,f,domain))
	eligibles.sort()
	eligibles.reverse()
	print len(eligibles)
	eligibles2=list(eligibles)
	for e in eligibles2:
		domains.append(e[2])
		if domains.count(e[2]) > 2: eligibles.remove(e)
	if finish:
		outstring=compile_kompas([x[1] for x in eligibles],limit=limit)
		file=open(os.path.join(readingdir,datetime.date.today().isoformat()+".txt"),"w")
		file.write(outstring)
		file.close()
	return eligibles[:limit]


def get_text(file,paragraphs=False):
		text=open(file).read()
		try: 
			text=text.split('="article_body">')[1].split("</div>",1)[0]
			text=unescape(text)
			text=text.replace("<p>","\n")
			text=re.sub("\<.*?\>","",text)
		except IndexError:
			return ""
		return text


		
def compile_kompas(files,limit=10,bolamax=2,femalemax=2): #list of complete paths
	outstring=""
	bola=0
	female=0
	y=0
	for f in files:
		y+=1
		if y > limit: break
		file=open(f).read()
		text=get_text(f,paragraphs=True).strip()
		text=unescape(text)
		try: 
			title=file.split("<title>")[1].split("</title>")[0].strip()
		except IndexError:
			try:
				title=file.split('title="')[1].split('"')[0].strip()
			except IndexError: 
				print "Error on "+f
				continue
		date=f.split("Kompas_")[1].split("\\")[0]
		outstring+="\n\n"+"\n".join([title,date,text])
	return outstring.encode("utf-8","ignore")
	
def daily(downdate=datetime.date.today(),nodown=False,voc=False):
	dir=False
	if not nodown:
		while not dir:
			dir=kompas(downdate)
			if not dir: print "failed..."
	else:
		dir=os.path.join(kdir,"Kompas_"+downdate.isoformat())
	files=[os.path.join(dir,x) for x in os.listdir(dir)]
	if voc is not False:
		xx=get_simple(files=files,finish=True,known=set([x.mainform for x in voc.allwords if x.successes]))
	else:
		xx=get_simple(files=files,finish=True)
	print xx
	return os.path.join(readingdir,downdate.isoformat()+".txt")

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
	
def neededwords(text,target=.95):
	known=get_blacklist(exclude=["blacklist.txt"])
	words=re.findall("\W([a-z]+[a-z\-]+[a-z]+)(?=\W)",text)
	words=[stem(x) for x in words]
	uniques=set(words)-known
	frequencies=[(words.count(x),x) for x in uniques]
	frequencies.sort()
	frequencies.reverse()
	total=len(words)
	unknown=[x for x in words if x not in known]
	coverage=len(words) - len(unknown)
	output=[]
	while coverage < (target * len(words)):
		new=frequencies[0]
		newword=new[1]
		output.append(newword)
		coverage+=new[0]
#		print str(float(coverage)/len(words)),newword
		frequencies.remove(new)
	return output
	
class Group:
	def __init__(self,maxsize=100,members=set(),tooclose=0.3):
		self.members=members
		self.glosses=set()
		self.wordcloud=set()
		self.max=maxsize
		self.tooclose=tooclose # minimum edit distance between members as divided by word length
#		self.toolong=5 # if two words share a sequence of this many letters, exclude
		self.storage=set()
	
	def __len__(self):
		return len(self.members)
	
	def glom(self,argument=""):
		if not argument:
			argument=self.members
		glomstring=" ".join(list(argument))
		return glomstring
	
	def ok2add(self,word,definition="",proceed=False,biglist=[],maxoverlap=1,worry_about_length=True):
		if len(self.members) >= self.max and worry_about_length:
			return False
		if word in self.glom():
			return False
		closes=[y for y in [(x,word,2.0*distance(x,word)/len(word+x)) for x in self.members] if y[2] < self.tooclose]
		if closes:
			print str(closes)
			return False
		elif definition and maxoverlap:
			if definition in self.glom(self.glosses):
				return False
			cloud=wordcloud(definition)
			if len(cloud.intersection(self.wordcloud)) >= maxoverlap:
				return False
		return True

	def add(self,word,definition="",tupled=False):
		self.members.add(word)
		self.glosses.add(definition)
		self.wordcloud|=wordcloud(definition)
		if tupled:
			self.storage.add(tupled)

def wordcloud(definition):
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
#		words=set(words)
		pass
	else:
		defined=words
		words=words.keys()
	if type(words[0]) != tuple:
#		wordlist=set([(x,words.index(x)) for x in words])
		wordlist=[(words.index(x),x) for x in words]
	else:
		wordlist=words
#		wordlist=set(words)
	wordlist.sort()
	print len(wordlist)
	for word in wordlist:
		w=word[1]
		print w,str(len(groups))
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

	
def updatesince(date):
	delta=datetime.timedelta(1)
	while date != datetime.date.today():
		date+=delta

def restore(filepath):
	words=[]
	defined={}
	samples={}
	file=open(filepath)
	for line in file:
		line=line.strip()
		if line.count("\t") != 2: continue
		lineparts=line.split("\t")
		words.append(lineparts[0])
		defined[lineparts[0]]=lineparts[1]
		samples[lineparts[0]]=lineparts[2]
	return words, samples, defined
	
def sederet(words,maxlen=9):
	defined=dict([(x,"") for x in words])
#cookielib setup
	cookiefile=("D:\\Code\\sederetcookies.lwp")
	cj=cookielib.LWPCookieJar()
	urlopen=urllib2.urlopen
	request=urllib2.Request
	if os.path.isfile(cookiefile):
		cj.load(cookiefile)
	opener = urllib2.build_opener(urllib2.HTTPCookieProcessor(cj))
	urllib2.install_opener(opener)
	txdata=''
	txheaders={'User-agent' : 'Mozilla/4.0 (compatible; MSIE 5.5; Windows NT)'}
	# first get "cookie"
	firsturl="http://vvv.sederet.com"
	firstpage=urllib2.urlopen(firsturl).read()
	cookievar=firstpage.split('name="var" value="')[1].split('"')[0]
	urlbase="http://vvv.sederet.com/translate.php?from_to=indo2eng&kata=%s&var="+cookievar
	if len(words) < 1+maxlen: chunks=[words]
	else:
		lastchunk=words[maxlen*(len(words)/maxlen):]
		tochunk=words[:maxlen*(len(words)/maxlen)]
		chunks=[words[x*maxlen:maxlen+x*maxlen] for x in range(0,len(words)/maxlen)]
		chunks.append(lastchunk)
	for c in chunks:
		if not c: continue
		querystring="+".join(c)
		if len(querystring) < 2: continue
		queryurl=urlbase % querystring
		request=urllib2.Request(queryurl,txdata,txheaders)
		print queryurl
		page=urllib2.urlopen(queryurl).read()
		defs=re.findall('\>([^\>]*?)\<\/a\>\<\/td\>\<td id\=[\"\\\']result\_td[\"\\\']\>(.*?)\<',page)
#		defs2=re.findall('\<span id\=[\"\\\']selected[\"\\\']\>(.*?)\<[\s\S]+?\<div id\=[\"\\\']translation[\"\\\']\>(.*?)\<\/div\>',page)
		print len(defs)
		print str(defs)
		for d in defs:
			if d[0] in c:
				defined[d[0]]=d[1]
			else:
				print "Unsupplied definiendum: "+d[0]
		file=open("D:\\lastfile.html","w")
		with file:
			file.write(page)
		time.sleep(choice([1,2,3]))
	return defined,defs

def frequentize(text,vocab=False,callme=False,param=False):
	words=text2words(text)
	wordset=set(words)-set(get_proper(words))
	freqs={}
	for w in wordset:
# lemmatization step?
		if w in freqs.keys():
			freqs[w]+=words.count(w)
		else:
			freqs[w]=words.count(w)
	if callme is not False:
		if param is False:
			callme()
		else:
			callme(freqs)
	return freqs
	
def get_proper(words):
	words=set(words)
	proper=[x for x in words if not x.islower() and x.lower() not in words]
	return set(proper)

def text2words(text):
	for p in punctuation:
		text=text.replace(p," ")
	rawwords=[x for x in re.split("[\r\s\n\t]+",text) if x.strip()]
	return rawwords
	
def listclean(listoftuples,cutoff=4):
	words=dict([(x[1],x[0]) for x in listoftuples])
	for w in words.keys():
		maybestem=""
		if len(w) < 5: continue
		if w.endswith("lah"):
			maybestem=w[:-3]
			if w.endswith("-lah"):
				maybestem=w[:-4]
		elif w.endswith("nya"):
			maybestem=w[:-3]
		elif w.startswith("di"):
			maybestem=w[2:]
		if maybestem and maybestem in words.keys():
			words[maybestem]+=words[w]
			del(words[w])
		if w.endswith("lah"):
			maybestem=w[:-3]
			if w.endswith("-lah"):
				maybestem=w[:-4]
		elif w.endswith("nya"):
			maybestem=w[:-3]
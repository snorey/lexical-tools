import os,re
import datetime,time
from htmlentitydefs import name2codepoint

from pie import Source

class Pais(Source):
	def __init__(self,date=datetime.date.today()-datetime.timedelta(1)): # Pais does not provide archive for current day
		Source.__init__(self,date=date,title="Pais",langcode="ES",subject="news")
		self.pattern='\<h3\>\<a href\=\"(.*?)\"'
		self.starturl="http://www.elpais.com/?d_date="+self.datestring
		self.throwout_unless=self.datestring # Pais dumps stories from multiple days in a single day's archive
		
	def fixurl(self,url):
		return "http://www.elpais.com"+url
		
	def filefromurl(self,url):
		return url.split("/")[-2]+".html"ate.today()-datetime.timedelta(1)): # Pais does not provide archive for current day
		Source.__init__(self,date=date,title="Pais",langcode="ES",subject="news")
		self.pattern='\<h3\>\<a href\=\"(.*?)\"'
		self.starturl="http://www.elpais.com/?d_date="+self.datestring
		self.throwout_unless=self.datestring # Pais dumps stories from multiple days
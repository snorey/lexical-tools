# -*- coding: utf-8 -*-

import os, re
import datetime, time
import urllib2, urllib
import unicodedata, random
from htmlentitydefs import name2codepoint

# -- Third-party modules -- #
import wx
import wx.lib.agw.piectrl
import wx.lib.scrolledpanel
from wx.html import HtmlWindow

# from nltk.corpus import wordnet as wn -- has to go server-side
from nltk.metrics import edit_distance as distance

import matplotlib
matplotlib.interactive( True )
matplotlib.use( 'WXAgg' )

# -- globals and such -- #

wordmatcher='(?<=\W)[a-z][a-z\-]+[a-z](?=\W)'
wx.SetDefaultPyEncoding("utf-8")

## from WordNet.corpus.stopwords.words("english"):
stops=set(['all', 'just', 'being', 'over', 'both', 'through', 'yourselves', 'its', 'before', 'herself', 'had', 'should', 'to', 'only', 'under', 'ours', 'has', 'do', 'them', 'his', 'very', 'they', 'not', 'during', 'now', 'him', 'nor', 'did', 'this', 'she', 'each', 'further', 'where', 'few', 'because', 'doing', 'some', 'are', 'our', 'ourselves', 'out', 'what', 'for', 'while', 'does', 'above', 'between', 't', 'be', 'we', 'who', 'were', 'here', 'hers', 'by', 'on', 'about', 'of', 'against', 's', 'or', 'own', 'into', 'yourself', 'down', 'your', 'from', 'her', 'their', 'there', 'been', 'whom', 'too', 'themselves', 'was', 'until', 'more', 'himself', 'that', 'but', 'don', 'with', 'than', 'those', 'he', 'me', 'myself', 'these', 'up', 'will', 'below', 'can', 'theirs', 'my', 'and', 'then', 'is', 'am', 'it', 'an', 'as', 'itself', 'at', 'have', 'in', 'any', 'if', 'again', 'no', 'when', 'same', 'how', 'other', 'which', 'you', 'after', 'most', 'such', 'why', 'a', 'off', 'I', 'yours', 'so', 'the', 'having', 'once']) 
try:
	workingdir=os.path.dirname( os.path.realpath( __file__ ) ) # doesn't work when compiled...
except:
	workingdir="."

class Nullity:
	pass

import sublime
import sublime_plugin
import urllib
import urllib2
import threading
import json
from StringIO import StringIO
import gzip

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), "beautifulsoup4-4.5.1"))

from bs4 import BeautifulSoup

query = ""
cur_result = 0
result_view = None

class SuboverflowCommand(sublime_plugin.TextCommand):
	def run(self, edit):
		global cur_result
		window = sublime.active_window()
		cur_result = 0
		window.show_input_panel("Sublime Overflow: ", "", self.create_query, None, None)

	def create_query(self, query):
		send_query = {'query': query}
		self.view.run_command('so', send_query)

class SoCommand(sublime_plugin.TextCommand):
	def run(self, edit, **args):
		global query
		query = ""
		if (args['query']): 
			query = args['query']
		thread = SubOverflowAsyncCall(query, 5)
		thread.start()

		self.handle_thread(thread, edit)

	def handle_thread(self, thread, edit, i = 0, dir = 1):
		next_thread = None
		if thread.is_alive():
			next_thread = thread
		elif thread.result == False:
			sublime.error_message('SubOverflow returned False')
		else:
			self.show_results(thread, edit)

		if next_thread:
			before = i % 8
			after = (7) - before
			if not after:
				dir = -1
			if not before:
				dir = 1
			i += dir
			self.view.set_status('suboverflow', 'SubOverflow [%s=%s]' % (' ' * before, ' ' * after))

			sublime.set_timeout(lambda: self.handle_thread(next_thread, edit, i, dir), 100)
			return

		self.view.erase_status('suboverflow')


	def show_results(self, thread, edit):
		global result_view
		if(result_view == None):
			self.window = sublime.active_window()
			result_view = self.window.new_file()
			result_view.set_name("result")
			result_view.set_scratch(True)
		else:
			result_view.erase(edit, sublime.Region(0, result_view.size()))
		result_edit = result_view.begin_edit()
		result_view.insert(result_edit, 0, thread.result)

class GetnextresultCommand(sublime_plugin.TextCommand):
	def run(self, edit):
		global query
		if(query != ""):
			global query
			send_query = {'query': query}
			self.view.run_command('so', send_query)

class SubOverflowAsyncCall(threading.Thread):
	def __init__(self, query, timeout):
		self.query = query
		self.timeout = timeout
		self.result = None
		threading.Thread.__init__(self)

	def run(self):
		try:
			global cur_result
			q = self.query.replace(' ', '+')
			url = 'https://api.stackexchange.com/2.2/search/advanced?order=desc&sort=activity&q=' + q + '&accepted=True&site=stackoverflow'
			request = urllib2.Request(url)
			request.add_header('Accept-encoding', 'gzip, deflate')
			response = urllib2.urlopen(request)
			data = response.read()
			buf = StringIO(data)
			f = gzip.GzipFile(fileobj=buf)
			data = f.read()
			result_obj = json.loads(data)
			objects = result_obj['items']
			if(len(objects) <= cur_result):
				cur_result = 0
			result_link = objects[cur_result]['link']
			cur_result += 1
			link_request = urllib2.Request(result_link)
			link_response = urllib2.urlopen(link_request)
			html_content = unicode(link_response.read(), 'utf-8')
			soup = BeautifulSoup(html_content, 'html.parser')
			result_display = ''
			title = soup.title.string
			result_display += title
			result_display += '\n'
			for i in title:
				result_display += '='
			result_display += '\n'
			question = soup.find("div", id="question")
			vote_count = question.find("span", {"class": "vote-count-post"}).contents
			result_display += 'Vote Count: ' + vote_count[0]
			result_display += '\n'
			question_content = question.find("div", {"class": "post-text"})
			for tag in question_content:
				if tag.name == 'p':
					result_display += str(tag)[3:-4] + '\n'
				elif tag.name == 'pre':
					result_display += '\n	' + str(tag)[11:-13] + '\n'
				elif tag.name == 'ul':
					for list_element in tag:
						if list_element.name == 'li':
							result_display += '	- ' + str(list_element)[4:-5] + '\n'
				else:
					result_display += str(tag) + '\n'

			answer_div = soup.find("div", id="answers")
			answers = answer_div.find_all("div", {"class": "answer"})
			for i, answer in enumerate(answers):
				result_display += 'Answer #' + str(i + 1) + '\n'
				result_display += '--------\n'
				answer_vote_count = answer.find("span", {"class": "vote-count-post"}).contents
				result_display += 'Vote Count: ' + answer_vote_count[0]
				accepted_answer = answer.find("span", {"class": "vote-accepted-on"})
				if accepted_answer:
					result_display += ' - ACCEPTED'
				result_display += '\n'
				answer_content = answer.find("div", {"class": "post-text"})
				for tag in answer_content:
					if tag.name == 'p':
						result_display += str(tag)[3:-4] + '\n'
					elif tag.name == 'pre':
						result_display += '\n	' + str(tag)[11:-13] + '\n'
					elif tag.name == 'ul' or tag.name == 'ol':
						for list_element in tag:
							if list_element.name == 'li':
								result_display += '	- ' + str(list_element)[4:-5] + '\n'
					else:
						result_display += str(tag) + '\n'
				result_display += '\n'

			result_display += '-' * 80
			result_display += '\nORIGINAL POST: ' + result_link
			self.result = result_display
			return

		except (urllib2.HTTPError) as (e):
			err = '%s: HTTP error %s contacting API' % (__name__, str(e.code))
		except (urllib2.URLError) as (e):
			err = '%s: URL error %s contacting API' % (__name__, str(e.reason))

		sublime.error_message(err)
		self.result = False

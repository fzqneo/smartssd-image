"""
CSV Table
Usage: N/A
Purpose: Takes data with any combination of different descriptors and formats them into a 2D table
		 based on a primary key declared upon initialization. Duplicate entries are overwritten
"""

# Globals -----------------------------------------------------------------------------------------
DEFAULT_PRIMARY_KEY = 'serial_number'

# -------------------------------------------------------------------------------------------------
# Client Table
# -------------------------------------------------------------------------------------------------
class CSVTable(object):
	def __init__(self, primary_key=DEFAULT_PRIMARY_KEY):
		self.num_col = 1
		self.num_row = 0
		self.debug = True
		self.primary_key = primary_key
		self.data = {self.primary_key:[]}

	def _format_error(self, msg):
		return "[CSVTable Error|"+str(msg).replace("\n",";")+"]"

	def add_col(self, field):
		"""
		Creates a new, empty column with the passed in field
		"""
		self.num_col += 1
		self.data[field] = ['None']*self.num_row

	def add_row(self):
		"""
		Adds a new, empty row with no information
		"""
		self.num_row += 1
		for field in self.data:
			self.data[field].append('None')

	def get_row(self, key):
		"""
		Retrieves all data available for the passed in key
		"""
		row = {}
		if key in self.data[self.primary_key]:
			index = self.data[self.primary_key].index(key)
		else:
			if self.debug:
				print self._format_error("Could not find key "+str(key)+" in data")
			return row
		for field in self.data:
			row[field]=str(self.data[field][index])
		return row

	def get_col(self, field):
		"""
		Retrieves the current data list for the passed in field
		"""
		output = []
		if field in list(self.data.keys()):
			for item in self.data[field]:
				output.append(str(item))
		return output

	def del_row(self, key):
		"""
		Removes any information related to the passed in key
		"""
		if key in self.data[self.primary_key]:
			index = self.data[self.primary_key].index(key)
			for field in self.data:
				del self.data[field][index]

	def del_col(self, field):
		"""
		Removes any information related to the passed in key
		"""
		del self.data[field]

	def insert_data(self, input_dict):
		"""
		Store information from the passed in dictionary, data must contain data for the
		primary key
		"""
		if self.primary_key not in input_dict:
			if self.debug:
				print self._format_error("No "+self.primary_key+", unable to store "+str(input_dict))
			return

		# Check if you're overwriting data or need a new row
		if input_dict[self.primary_key] not in self.data[self.primary_key]:
			row_num = self.num_row
			self.add_row()
		else:
			row_num = self.data[self.primary_key].index(input_dict[self.primary_key])

		# For every field passed in, insert the information available (add a new column if needed)
		for field in input_dict:
			if field not in self.data:
				self.add_col(field)
			self.data[field][row_num]=input_dict[field]

	def print_table(self, header=[]):
		"""
		Print out the current information according to the passed in header, if an empty list is
		passed in then print all fields available with the primary key first
		If you put '*' in a header descriptor then any field available that contains the string
		(without the '*' character in it) will be added
		"""
		header = self._create_header(header)
		print ",".join(header)
		for key in self.data[self.primary_key]:
			key_data = self.get_row(key)
			output_data = []
			for field in header:
				if field in key_data:
					output_data.append(key_data[field])
				else:
					output_data.append('None')
			print ",".join(output_data)

	def _create_header(self, header):
		# Formats the header either by creating the default one or finding matching strings for
		# fields that contain '*'
		if not header:
			header = sorted(list(self.data.keys()))
			header.insert(0, header.pop(header.index(self.primary_key)))
			return header
		temp = []
		for field in header:
			if '*' in field:
				key = field.replace("*","")
				temp += filter(lambda x:key in x, self.data.keys())
			else:
				temp += [field]
		return temp
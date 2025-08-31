from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, IntegerField, TextAreaField, BooleanField, FileField, SelectMultipleField
from wtforms.validators import DataRequired, URL, NumberRange, Optional
from wtforms.widgets import CheckboxInput, ListWidget
from flask_wtf.file import FileAllowed

class MultiCheckboxField(SelectMultipleField):
    widget = ListWidget(prefix_label=False)
    option_widget = CheckboxInput()

class CrawlerForm(FlaskForm):
    url = StringField('Target URL', validators=[DataRequired(), URL()], 
                     render_kw={"placeholder": "https://example.com"})
    
    depth = SelectField('Crawl Depth', 
                       choices=[
                           ('1', '1 - Main page only'),
                           ('2', '2 - Main sections'),
                           ('3', '3 - Subsections'),
                           ('4', '4 - Deep content'),
                           ('5', '5 - Full crawl')
                       ], 
                       default='2')
    
    delay = IntegerField('Request Delay (seconds)', validators=[NumberRange(min=1, max=10)], default=2,
                        render_kw={"min": "1", "max": "10"})
    
    threads = IntegerField('Concurrent Threads', validators=[NumberRange(min=1, max=50)], default=10,
                          render_kw={"min": "1", "max": "50"})
    
    extensions = StringField('File Extensions Filter', 
                           render_kw={"placeholder": ".pdf,.doc,.txt (leave empty for all)"})

class BruteForceForm(FlaskForm):
    fuzz_url = StringField('Fuzzing Target (use FUZZ)', validators=[DataRequired()], 
                          render_kw={"placeholder": "https://example.com/FUZZ or https://FUZZ.example.com"})
    
    wordlist_file = FileField('Wordlist File', validators=[Optional(), FileAllowed(['txt'], 'Only .txt files allowed!')])
    
    wordlist_path = StringField('Wordlist Path', validators=[Optional()],
                               render_kw={"placeholder": "Or enter path to wordlist file"})
    
    threads = IntegerField('Threads', validators=[NumberRange(min=1, max=200)], default=40,
                          render_kw={"min": "1", "max": "200"})
    
    status_codes = MultiCheckboxField('Status Codes (-mc)', 
                                     choices=[
                                         ('200', '200 - OK'),
                                         ('204', '204 - No Content'),
                                         ('301', '301 - Moved Permanently'),
                                         ('302', '302 - Found'),
                                         ('307', '307 - Temporary Redirect'),
                                         ('401', '401 - Unauthorized'),
                                         ('403', '403 - Forbidden'),
                                         ('500', '500 - Internal Server Error')
                                     ],
                                     default=['200', '301', '302', '307', '403'])
    
    recursion = BooleanField('Enable Recursion', default=False)
    
    recursion_depth = IntegerField('Recursion Depth', validators=[NumberRange(min=1, max=10)], default=2,
                                  render_kw={"min": "1", "max": "10"})
    
    timeout = IntegerField('Timeout (seconds)', validators=[NumberRange(min=1, max=30)], default=10)

class MetadataForm(FlaskForm):
    # File upload method
    files = FileField('Upload Files', validators=[Optional()], 
                     render_kw={"multiple": True})
    
    # Directory input method
    input_directory = StringField('Input Directory Path', validators=[Optional()],
                                 render_kw={"placeholder": "Path to directory containing files to analyze"})
    
    output_file = StringField('Output JSON File Path', validators=[Optional()],
                             render_kw={"placeholder": "Leave empty to display results only"})
    
    # Analysis options
    extract_exif = BooleanField('Extract EXIF Data', default=True)
    
    calculate_hashes = BooleanField('Calculate File Hashes (MD5, SHA1, SHA256)', default=True)
    
    deep_analysis = BooleanField('Deep File Analysis', default=False)
    
    # File type filters
    analyze_images = BooleanField('Analyze Images', default=True)
    
    analyze_documents = BooleanField('Analyze Documents', default=True)
    
    analyze_executables = BooleanField('Analyze Executables', default=False)

class DownloadForm(FlaskForm):
    # URL input methods
    urls = TextAreaField('URLs to Download (one per line)', validators=[Optional()],
                        render_kw={"rows": 8, "placeholder": "https://example.com/file1.pdf\nhttps://example.com/file2.doc"})
    
    url_file = StringField('URL File Path', validators=[Optional()],
                          render_kw={"placeholder": "Path to text file containing URLs"})
    
    output_directory = StringField('Output Directory', validators=[Optional()],
                                  render_kw={"placeholder": "Leave empty for default downloads folder"})
    
    max_size = IntegerField('Max File Size (MB)', validators=[NumberRange(min=1, max=1000)], default=100,
                           render_kw={"min": "1", "max": "1000"})
    
    threads = IntegerField('Concurrent Downloads', validators=[NumberRange(min=1, max=20)], default=5,
                          render_kw={"min": "1", "max": "20"})
    
    timeout = IntegerField('Download Timeout (seconds)', validators=[NumberRange(min=5, max=300)], default=30)

class WordlistDownloadForm(FlaskForm):
    download_path = StringField('Download Directory', validators=[Optional()],
                               render_kw={"placeholder": "Leave empty for default location"})
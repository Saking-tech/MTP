import sys
import os
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *
import socketio
import speech_recognition as sr
import time
from groq import Groq
from gtts import gTTS
import tempfile
from pygame import mixer

GROQ_API_KEY = ""
# Add LANGUAGES dictionary as provided
LANGUAGES = {
    'Afrikaans': 'af', 'Amharic': 'am', 'Bulgarian': 'bg', 'Bosnian': 'bs',
    'Arabic': 'ar', 'Bengali': 'bn', 'Catalan': 'ca', 'Czech': 'cs', 'Welsh': 'cy', 'Danish': 'da', 'German': 'de', 'Greek': 'el', 'English': 'en', 'Spanish': 'es', 'Estonian': 'et', 'Basque': 'eu', 'Finnish': 'fi', 'French': 'fr', 'French (Canada)': 'fr-CA', 'Galician': 'gl', 'Gujarati': 'gu', 'Hausa': 'ha', 'Hindi': 'hi', 'Croatian': 'hr', 'Hungarian': 'hu', 'Indonesian': 'id', 'Icelandic': 'is', 'Italian': 'it', 'Hebrew': 'iw', 'Japanese': 'ja', 'Javanese': 'jw', 'Khmer': 'km', 'Kannada': 'kn', 'Korean': 'ko', 'Latin': 'la', 'Lithuanian': 'lt', 'Latvian': 'lv', 'Malayalam': 'ml', 'Marathi': 'mr', 'Malay': 'ms', 'Myanmar (Burmese)': 'my', 'Nepali': 'ne', 'Dutch': 'nl', 'Norwegian': 'no', 'Punjabi (Gurmukhi)': 'pa', 'Polish': 'pl', 'Portuguese (Brazil)': 'pt', 'Portuguese (Portugal)': 'pt-PT', 'Romanian': 'ro', 'Russian': 'ru', 'Sinhala': 'si', 'Slovak': 'sk', 'Albanian': 'sq', 'Serbian': 'sr', 'Sundanese': 'su', 'Swedish': 'sv', 'Swahili': 'sw', 'Tamil': 'ta', 'Telugu': 'te', 'Thai': 'th', 'Filipino': 'tl', 'Turkish': 'tr', 'Ukrainian': 'uk', 'Urdu': 'ur', 'Vietnamese': 'vi', 'Cantonese': 'yue', 'Chinese (Simplified)': 'zh-CN', 'Chinese (Traditional)': 'zh-TW'
}

class UserInfoDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Join Chat Room')
        self.setFixedWidth(400)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        # Form layout
        form = QFormLayout()

        # Username field
        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("Enter your username")
        form.addRow("Username:", self.username_input)

        # Language selection
        self.language_combo = QComboBox()
        self.language_combo.addItems(sorted(LANGUAGES.keys()))
        self.language_combo.setCurrentText('English')
        form.addRow("Language:", self.language_combo)

        # Room name field
        self.room_input = QLineEdit()
        self.room_input.setPlaceholderText("Enter room name")
        form.addRow("Room:", self.room_input)

        layout.addLayout(form)

        # Error label
        self.error_label = QLabel()
        self.error_label.setStyleSheet("color: red;")
        self.error_label.hide()
        layout.addWidget(self.error_label)

        # Buttons
        buttons = QHBoxLayout()
        join_button = QPushButton("Join")
        cancel_button = QPushButton("Cancel")

        join_button.clicked.connect(self.validate_and_accept)
        cancel_button.clicked.connect(self.reject)

        buttons.addWidget(join_button)
        buttons.addWidget(cancel_button)
        layout.addLayout(buttons)

        # Style
        self.setStyleSheet("""
            QDialog {
                background-color: white;
            }
            QLineEdit, QComboBox {
                padding: 8px;
                border: 1px solid #bdc3c7;
                border-radius: 5px;
                min-width: 200px;
            }
            QPushButton {
                padding: 8px 20px;
                background-color: #3498db;
                color: white;
                border: none;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
            QPushButton[text="Cancel"] {
                background-color: #95a5a6;
            }
            QPushButton[text="Cancel"]:hover {
                background-color: #7f8c8d;
            }
        """)

    def validate_and_accept(self):
        username = self.username_input.text().strip()
        room = self.room_input.text().strip()

        if not username:
            self.show_error("Please enter a username")
            return
        if not room:
            self.show_error("Please enter a room name")
            return

        self.accept()

    def show_error(self, message):
        self.error_label.setText(message)
        self.error_label.show()

    def get_data(self):
        return {
            'username': self.username_input.text().strip(),
            'language': self.language_combo.currentText(),
            'room': self.room_input.text().strip()
        }

class TranslationManager:
    def __init__(self, groq_api_key):
        self.groq_client = Groq(api_key=groq_api_key)
    def translate_text(self, text, source_language, target_language):
        """
        Translate text from source language to target language
        """
        try:
            prompt = f"""Translate the following text into {target_language}: {text} . Only Return the Translation of the {text} and Nothing except the Translation. Keep in mind You have to Completely Translate the text"""
            completion = self.groq_client.chat.completions.create(
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                model="llama-3.3-70b-versatile", #meta-llama/llama-4-maverick-17b-128e-instruct, llama-3.1-8b-instant, llama-3.3-70b-versatile, deepseek-r1-distill-llama-70b
                temperature=0.7,
                max_tokens= 1000
            )
            translation = completion.choices[0].message.content
            return translation
        except Exception as e:
            print(f"Translation error: {e}")
            return text  # Return original text if translation fails
    def get_language_code(self, language_name):
        """Get language code from language name"""
        return LANGUAGES.get(language_name, 'en')

class VoiceManager:
    def __init__(self):
        self.recognizer = sr.Recognizer()
        self.recognizer.energy_threshold = 300
        self.recognizer.dynamic_energy_threshold = True
        self.recognizer.pause_threshold = 1.0

    def speech_to_text(self, audio_data, language_code='en-US'):
        """Convert speech to text in specified language"""
        try:
            text = self.recognizer.recognize_google(
                audio_data, language=language_code)
            return text
        except sr.UnknownValueError:
            return None
        except sr.RequestError as e:
            print(f"Speech recognition error: {e}")
            return None

    def text_to_speech(self, text, language_code):
        """Convert text to speech in specified language"""
        try:
            temp_file = tempfile.NamedTemporaryFile(
                delete=False, suffix='.mp3')
            temp_filename = temp_file.name
            temp_file.close()

            tts = gTTS(text=text, lang=language_code)
            tts.save(temp_filename)

            mixer.init()
            mixer.music.load(temp_filename)
            mixer.music.play()

            while mixer.music.get_busy():
                time.sleep(0.1)

            mixer.quit()
            os.remove(temp_filename)
            return True
        except Exception as e:
            print(f"Text-to-speech error: {e}")
            return False

class Message:
    def __init__(self, text, username, source_language, timestamp):
        self.text = text
        self.username = username
        self.source_language = source_language
        self.timestamp = timestamp
        self.translations = {}  # Store translations for different languages

    def add_translation(self, language, translated_text):
        self.translations[language] = translated_text

    def get_translation(self, target_language):
        return self.translations.get(target_language, self.text)

    def to_dict(self):
        return {
            'text': self.text,
            'username': self.username,
            'source_language': self.source_language,
            'timestamp': self.timestamp,
            'translations': self.translations
        }

    @classmethod
    def from_dict(cls, data):
        message = cls(
            text=data['text'],
            username=data['username'],
            source_language=data['source_language'],
            timestamp=data['timestamp']
        )
        message.translations = data.get('translations', {})
        return message

class ChatRoom:
    def __init__(self, room_name):
        self.room_name = room_name
        self.users = {}  # {user_id: {'username': name, 'language': lang}}
        self.messages = []
        self.translation_manager = TranslationManager(GROQ_API_KEY)
        self.voice_manager = VoiceManager()

    async def add_user(self, user_id, username, preferred_language):
        """Add user to the room with their preferred language"""
        self.users[user_id] = {
            'username': username,
            'language': preferred_language
        }

    def remove_user(self, user_id):
        """Remove user from the room"""
        if user_id in self.users:
            del self.users[user_id]

    async def process_message(self, text, username, source_language):
        """Process and translate message for all users"""
        timestamp = time.strftime('%H:%M:%S')
        message = Message(text, username, source_language, timestamp)
        # Translate for each unique language in the room
        target_languages = set(user['language']
                               for user in self.users.values())
        for target_lang in target_languages:
            if target_lang != source_language:
                translated_text = await self.translation_manager.translate_text(
                    text, source_language, target_lang)
                message.add_translation(target_lang, translated_text)
            # if target_lang == source_language:
            #     translated_text = await self.translation_manager.translate_text(
            #         text, source_language, target_lang)
            #     message.add_translation(target_lang, translated_text)
        self.messages.append(message)
        return message

    def get_messages_for_user(self, preferred_language):
        """Get all messages translated to user's preferred language"""
        translated_messages = []
        for message in self.messages:
            translated_text = message.get_translation(preferred_language)
            translated_messages.append({
                'text': translated_text,
                'original_text': message.text,
                'username': message.username,
                'timestamp': message.timestamp,
                'is_translation': message.source_language != preferred_language
            })
        return translated_messages

class SpeechThread(QThread):
    finished = pyqtSignal(str)
    status = pyqtSignal(str)

    def __init__(self, language_code):
        super().__init__()
        self.language_code = language_code
        self.recognizer = sr.Recognizer()
        self.recognizer.energy_threshold = 300
        self.recognizer.dynamic_energy_threshold = True
        self.recognizer.pause_threshold = 2.0  # Longer pause threshold for VAD
        self.is_recording = False

    def run(self):
        try:
            with sr.Microphone() as source:
                self.status.emit(
                    "Preparing to listen... Adjusting for background noise...")
                self.recognizer.adjust_for_ambient_noise(source, duration=1)
                self.status.emit(
                    "🎤 Listening... Speak clearly (Recording will stop after silence)")
                audio_chunks = []
                start_time = time.time()
                silence_threshold = 2.0
                last_sound_time = start_time
                while self.is_recording:
                    try:
                        audio_chunk = self.recognizer.listen(
                            source,
                            timeout=1,
                            phrase_time_limit=10
                        )
                        audio_chunks.append(audio_chunk)
                        last_sound_time = time.time()
                        self.status.emit("Recording... 🎵")
                        current_time = time.time()
                        if current_time - last_sound_time > silence_threshold:
                            self.status.emit(
                                "Silence detected, stopping recording")
                            break
                    except sr.WaitTimeoutError:
                        current_time = time.time()
                        if current_time - last_sound_time > silence_threshold:
                            self.status.emit(
                                "Silence detected, stopping recording")
                            break
                        continue
                if audio_chunks:
                    self.status.emit("Processing speech...")
                    # Combine audio chunks
                    combined_audio = self.combine_audio_data(audio_chunks)
                    text = self.recognizer.recognize_google(
                        combined_audio,
                        language=self.language_code)
                    self.finished.emit(text)
                else:
                    self.status.emit("No speech detected")
                    self.finished.emit("")
        except Exception as e:
            self.status.emit(f"Error: {str(e)}")
            self.finished.emit("")
        finally:
            self.is_recording = False

    def combine_audio_data(self, audio_chunks):
        """Combine multiple audio chunks into a single AudioData object"""
        if not audio_chunks:
            return None
        first_chunk = audio_chunks[0]
        sample_width = first_chunk.sample_width
        sample_rate = first_chunk.sample_rate
        combined_data = b''
        for chunk in audio_chunks:
            combined_data += chunk.frame_data
        return sr.AudioData(combined_data, sample_rate, sample_width)
    def stop(self):
        self.is_recording = False

class MainApplication(QMainWindow):
    message_received = pyqtSignal(dict)
    status_update = pyqtSignal(str)
    users_update = pyqtSignal(list)

    def __init__(self):
        super().__init__()
        self.init_managers()
        self.get_user_info()
        self.setup_socket()
        self.init_ui()
        self.connect_signals()
        self.connect_to_server()

    def init_managers(self):
        """Initialize managers and basic state"""
        self.translation_manager = TranslationManager(GROQ_API_KEY)
        self.voice_manager = VoiceManager()
        self.sio = socketio.Client()
        self.username = None
        self.room = None
        self.preferred_language = None
        self.speech_thread = None

    def get_user_info(self):
        """Get user information before connecting"""
        dialog = UserInfoDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            data = dialog.get_data()
            self.username = data['username']
            self.preferred_language = data['language']
            self.room = data['room']
            return True
        return False

    def setup_socket(self):
        """Setup socket.io event handlers"""
        @self.sio.on('connect')
        def on_connect():
            self.status_update.emit(f'{self.username} Connected')
            self.sio.emit('join_room', {
                'room': self.room,
                'username': self.username,
                'language': self.preferred_language
            })

        @self.sio.on('message')
        def on_message(data):
            if data.get('room') == self.room:  # Only show messages from current room
                self.message_received.emit(data)

        @self.sio.on('users_list')
        def on_users_list(users):
            self.users_update.emit(users)

        @self.sio.on('disconnect')
        def on_disconnect():
            self.status_update.emit("Disconnected from server")

    def init_ui(self):
        """Initialize the user interface"""
        self.setWindowTitle('Multilingual Voice Chat')
        self.setGeometry(100, 100, 800, 680)

        # Main widget
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout(main_widget)

        # Top buttons row
        top_buttons = QHBoxLayout()

        # Disconnect button
        self.disconnect_button = QPushButton('❌ Disconnect')
        self.disconnect_button.clicked.connect(self.handle_disconnect)
        self.disconnect_button.setStyleSheet("""
            QPushButton {
                background-color: #e74c3c;
                color: white;
                padding: 8px;
                border: none;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #c0392b;
            }
        """)
        top_buttons.addWidget(self.disconnect_button)

        # Join New Room button
        self.join_room_button = QPushButton('🚪 Join Another Room')
        self.join_room_button.clicked.connect(self.show_join_room_dialog)
        self.join_room_button.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                padding: 8px;
                border: none;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
        """)
        top_buttons.addWidget(self.join_room_button)

        # Add top buttons to layout
        layout.addLayout(top_buttons)

        # Status bar
        self.status_label = QLabel('Connecting...')
        layout.addWidget(self.status_label)

        # Main content area
        content = QHBoxLayout()

        # Chat area
        chat_container = self.create_chat_area()
        content.addLayout(chat_container, stretch=7)
        self.download_button = QPushButton('📥 Download Transcript')
        self.download_button.clicked.connect(self.download_transcript)
        self.download_button.setStyleSheet("""
            QPushButton {
                background-color: #27ae60;
                color: white;
                padding: 8px;
                border: none;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #219a52;
            }
        """)
        top_buttons.addWidget(self.download_button)

        # Users list
        users_container = self.create_users_list()
        content.addLayout(users_container, stretch=3)

        layout.addLayout(content)

    def handle_disconnect(self):
        """Handle disconnection from current room"""
        try:
            if self.sio.connected:
                self.sio.emit('leave_room', {
                    'room': self.room,
                    'username': self.username
                })
                self.sio.disconnect()

            # Clear the chat
            while self.messages_layout.count() > 1:
                item = self.messages_layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()

            # Clear users list
            self.users_list.clear()

            # Show join dialog
            if self.get_user_info():
                self.connect_to_server()
            else:
                self.close()

        except Exception as e:
            QMessageBox.warning(self, "Disconnection Error", f"Error during disconnection: {str(e)}")
    
    def show_join_room_dialog(self):
        """Show dialog for joining a new room"""
        try:
            # Create input dialog for new room
            new_room, ok = QInputDialog.getText(
                self,
                'Join New Room',
                'Enter new room name:',
                QLineEdit.Normal
            )

            if ok and new_room.strip():
                # Leave current room
                self.sio.emit('leave_room', {
                    'room': self.room,
                    'username': self.username
                })

                # Clear current chat
                while self.messages_layout.count() > 1:
                    item = self.messages_layout.takeAt(0)
                    if item.widget():
                        item.widget().deleteLater()

                # Clear users list
                self.users_list.clear()

                # Join new room
                self.room = new_room.strip()
                self.sio.emit('join_room', {
                    'room': self.room,
                    'username': self.username,
                    'language': self.preferred_language
                })

                self.status_update.emit(f"Joined room: {self.room}")

        except Exception as e:
            QMessageBox.warning(self, "Room Change Error", f"Error changing rooms: {str(e)}")
    
    def create_chat_area(self):
        """Create the chat area with messages and controls"""
        container = QVBoxLayout()

        # Top buttons row
        top_buttons = QHBoxLayout()

        # Disconnect button
        self.disconnect_button = QPushButton('❌ Disconnect')
        self.disconnect_button.clicked.connect(self.handle_disconnect)
        self.disconnect_button.setStyleSheet("""
            QPushButton {
                background-color: #e74c3c;
                color: white;
                padding: 8px;
                border: none;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #c0392b;
            }
        """)
        top_buttons.addWidget(self.disconnect_button)

        # Join New Room button
        self.join_room_button = QPushButton('🚪 Join Another Room')
        self.join_room_button.clicked.connect(self.show_join_room_dialog)
        self.join_room_button.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                padding: 8px;
                border: none;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
        """)
        top_buttons.addWidget(self.join_room_button)

        # Add top buttons to container
        container.addLayout(top_buttons)

        # Rest of your existing code...
        self.messages_area = QScrollArea()
        self.messages_area.setWidgetResizable(True)
        self.messages_widget = QWidget()
        self.messages_layout = QVBoxLayout(self.messages_widget)
        self.messages_layout.addStretch()
        self.messages_area.setWidget(self.messages_widget)
        container.addWidget(self.messages_area)

        # Your existing controls...
        controls = QHBoxLayout()
        """Create the chat area with messages and controls"""

        # Voice button
        self.speak_button = QPushButton('🎤 Hold to Speak')
        self.speak_button.pressed.connect(self.start_speaking)
        self.speak_button.released.connect(self.stop_speaking)
        controls.addWidget(self.speak_button)

        # Auto-play toggle
        self.auto_play = QCheckBox('Auto-play translations')
        self.auto_play.setChecked(True)
        controls.addWidget(self.auto_play)

        container.addLayout(controls)
        return container

    def create_users_list(self):
        """Create the users list panel"""
        container = QVBoxLayout()

        users_label = QLabel('Users in Room')
        container.addWidget(users_label)

        self.users_list = QListWidget()
        container.addWidget(self.users_list)

        return container

    def connect_signals(self):
        """Connect all signals to slots"""
        self.message_received.connect(self.handle_message)
        self.status_update.connect(self.update_status)
        self.users_update.connect(self.update_users)

    def connect_to_server(self):
        """Connect to the socket.io server"""
        try:
            self.sio.connect('http://localhost:5000') #('https://nodejs-serverless-function-express-1-t7h0.onrender.com') #Local to Online ('http://localhost:5000')
        except Exception as e:
            QMessageBox.critical(self, "Connection Error",
                                 f"Could not connect to server: {str(e)}")
            sys.exit()

    def start_speaking(self):
        """Start recording speech"""
        if not self.speech_thread:
            self.speak_button.setStyleSheet("background-color: #e74c3c;")
            self.speech_thread = SpeechThread(
                LANGUAGES[self.preferred_language])
            self.speech_thread.finished.connect(self.handle_speech)
            self.speech_thread.start()

    def stop_speaking(self):
        """Stop recording speech"""
        if self.speech_thread:
            self.speech_thread.stop()
            self.speech_thread = None
            self.speak_button.setStyleSheet("")

    def handle_speech(self, text):
        """Handle recorded speech"""
        if text:
            self.sio.emit('message', {
                'text': text,
                'username': self.username,
                'source_language': self.preferred_language,
                'room': self.room
            })

    def handle_message(self, data):
        """Handle received message"""
        # If message is in different language, translate it
        if data['source_language'] != self.preferred_language:
            try:
                translated_text = self.translation_manager.translate_text(
                    data['text'],
                    data['source_language'],
                    self.preferred_language
                )
                data['translated_text'] = translated_text

                # Auto-play translation if enabled
                if self.auto_play.isChecked() and data['username'] != self.username:
                    self.voice_manager.text_to_speech(
                        translated_text,
                        LANGUAGES[self.preferred_language]
                    )
            except Exception as e:
                print(f"Translation error: {e}")
                # Use original text if translation fails
                data['translated_text'] = data['text']
        if data['source_language'] == self.preferred_language:
            try:
                translated_text = data['text']
                # Auto-play translation if enabled
                if self.auto_play.isChecked() and data['username'] != self.username:
                    self.voice_manager.text_to_speech(
                        translated_text,
                        LANGUAGES[self.preferred_language]
                    )
            except Exception as e:
                print(f"Translation error: {e}")
                # Use original text if translation fails
                data['translated_text'] = data['text']

        self.add_message_to_chat(data)

    def add_message_to_chat(self, data):
        """Add message to chat area"""
        # Create message widget
        message_widget = QWidget()
        message_layout = QVBoxLayout(message_widget)

        # Header (username and timestamp)
        header = QLabel(f"{data['username']} ({data['timestamp']})")
        message_layout.addWidget(header)

        # Original text
        text_label = QLabel(data['text'])
        text_label.setWordWrap(True)
        message_layout.addWidget(text_label)

        # Translation if available
        if 'translated_text' in data:
            trans_label = QLabel(f"Translation: {data['translated_text']}")
            trans_label.setWordWrap(True)
            trans_label.setStyleSheet("color: #666; font-style: italic;")
            message_layout.addWidget(trans_label)

        # Add message to chat
        self.messages_layout.insertWidget(
            self.messages_layout.count() - 1,
            message_widget
        )

        # Scroll to bottom
        QTimer.singleShot(100, lambda: self.messages_area.verticalScrollBar().setValue(
            self.messages_area.verticalScrollBar().maximum()
        ))

    def update_status(self, status):
        """Update status label"""
        self.status_label.setText(status)

    def update_users(self, users):
        """Update users list"""
        self.users_list.clear()
        for user in users:
            self.users_list.addItem(
                f"🎤 {user['username']} ({user['language']})"
            )

    def create_chat_area(self):
        """Create the chat area with messages and controls"""
        container = QVBoxLayout()

        # Messages area
        self.messages_area = QScrollArea()
        self.messages_area.setWidgetResizable(True)
        self.messages_widget = QWidget()
        self.messages_layout = QVBoxLayout(self.messages_widget)
        self.messages_layout.addStretch()
        self.messages_area.setWidget(self.messages_widget)
        container.addWidget(self.messages_area)

        # Controls
        controls = QHBoxLayout()

        # Voice button (now a toggle button)
        self.speak_button = QPushButton('🎤 Speak')
        self.speak_button.setCheckable(True)  # Make it toggleable
        self.speak_button.clicked.connect(self.toggle_recording)
        self.speak_button.setStyleSheet("""
            QPushButton {
                background-color: #2ecc71;
                color: white;
                padding: 10px;
                border: none;
                border-radius: 5px;
                font-size: 14px;
            }
            QPushButton:checked {
                background-color: #e74c3c;
            }
        """)
        controls.addWidget(self.speak_button)

        # Auto-play toggle
        self.auto_play = QCheckBox('Auto-play translations')
        self.auto_play.setChecked(True)
        controls.addWidget(self.auto_play)

        container.addLayout(controls)
        return container

    def toggle_recording(self):
        """Toggle recording on/off"""
        if self.speak_button.isChecked():
            # Start recording
            self.speak_button.setText('🎤 Stop Speaking ')
            if not self.speech_thread:
                self.speech_thread = SpeechThread(
                    LANGUAGES[self.preferred_language])
                self.speech_thread.finished.connect(
                    self.handle_speech_finished)
                self.speech_thread.status.connect(self.update_status)
                self.speech_thread.is_recording = True
                self.speech_thread.start()
        else:
            # Stop recording
            self.speak_button.setText('🎤 Speak')
            if self.speech_thread:
                self.speech_thread.stop()

    def handle_speech_finished(self, text):
        """Handle the finished speech recognition"""
        self.speak_button.setChecked(False)
        self.speak_button.setText('🎤 Speak')
        self.speech_thread = None

        if text:
            self.sio.emit('message', {
                'text': text,
                'username': self.username,
                'source_language': self.preferred_language,
                'room': self.room
            })
        else:
            self.status_update.emit("No speech detected or error occurred")

    def download_transcript(self):
        """Download chat transcript as a text file"""
        try:
            filename, _ = QFileDialog.getSaveFileName(
                self,
                "Save Chat Transcript",
                "",
                "Text Files (*.txt);;All Files (*)"
            )

            if filename:
                with open(filename, 'w', encoding='utf-8') as f:
                    # Iterate through message widgets in the chat area
                    for i in range(self.messages_layout.count() - 1):  # -1 to skip the stretch
                        widget = self.messages_layout.itemAt(i).widget()
                        if widget:
                            # Get all labels in the message widget
                            labels = widget.findChildren(QLabel)
                            message_text = []
                            for label in labels:
                                message_text.append(label.text())
                            f.write('\n'.join(message_text) + '\n\n')

                QMessageBox.information(
                    self,
                    "Success",
                    "Chat transcript saved successfully!"
                )
        except Exception as e:
            QMessageBox.warning(
                self,
                "Error",
                f"Failed to save transcript: {str(e)}"
            )
    
    def closeEvent(self, event):
        """Handle application closure"""
        if self.speech_thread:
            self.speech_thread.stop()
            self.speech_thread.wait()
        if self.sio.connected:
            self.sio.disconnect()
        event.accept()


def main():
    app = QApplication(sys.argv)
    window = MainApplication()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()


# pyinstaller --name="MTP" --onefile --windowed --icon=Translator.ico --clean --noupx --noconfirm --noconsole Final_application.py

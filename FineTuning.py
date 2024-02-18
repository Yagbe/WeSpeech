import os
import tkinter as tk
from tkinter import ttk
from google.cloud import speech, translate_v2 as translate, texttospeech
from google.oauth2 import service_account
import pyaudio
from six.moves import queue
import io
from pydub import AudioSegment
from pydub.playback import play

# Set up Google Cloud credentials
client_file = 'sa_speech.json'
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = client_file
credentials = service_account.Credentials.from_service_account_file(client_file)

# Initialize clients for Google Cloud services
speech_client = speech.SpeechClient(credentials=credentials)
translate_client = translate.Client()
text_to_speech_client = texttospeech.TextToSpeechClient()

# Audio recording parameters
RATE = 16000
CHUNK = int(RATE / 10)  # 100ms

class MicrophoneStream(object):
    """Opens a recording stream as a generator yielding the audio chunks."""
    def __init__(self, rate, chunk):
        self._rate = rate
        self._chunk = chunk
        self._buff = queue.Queue()
        self.closed = True

    def __enter__(self):
        self._audio_interface = pyaudio.PyAudio()
        self._audio_stream = self._audio_interface.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=self._rate,
            input=True,
            frames_per_buffer=self._chunk,
            stream_callback=self._fill_buffer,
        )
        self.closed = False
        return self

    def __exit__(self, type, value, traceback):
        self._audio_stream.stop_stream()
        self._audio_stream.close()
        self.closed = True
        self._buff.put(None)
        self._audio_interface.terminate()

    def _fill_buffer(self, in_data, frame_count, time_info, status_flags):
        """Continuously collect data from the audio stream, into the buffer."""
        self._buff.put(in_data)
        return None, pyaudio.paContinue

    def generator(self):
        while not self.closed:
            chunk = self._buff.get()
            if chunk is None:
                return
            data = [chunk]

            while True:
                try:
                    chunk = self._buff.get(block=False)
                    if chunk is None:
                        return
                    data.append(chunk)
                except queue.Empty:
                    break

            yield b''.join(data)

def translate_text(text, target_language="en"):
    result = translate_client.translate(text, target_language=target_language)
    return result['translatedText']

def text_to_speech(text, language_code="en-US", gender=texttospeech.SsmlVoiceGender.NEUTRAL):
    synthesis_input = texttospeech.SynthesisInput(text=text)
    voice = texttospeech.VoiceSelectionParams(language_code=language_code, ssml_gender=gender)
    audio_config = texttospeech.AudioConfig(audio_encoding=texttospeech.AudioEncoding.MP3)
    response = text_to_speech_client.synthesize_speech(input=synthesis_input, voice=voice, audio_config=audio_config)
    audio_mp3 = io.BytesIO(response.audio_content)
    audio_mp3.seek(0)
    song = AudioSegment.from_file(audio_mp3, format="mp3")
    play(song)

def listen_print_loop(responses, target_language="ko", tts_language_code="ko"):
    for response in responses:
        if not response.results:
            continue

        result = response.results[0]
        if not result.alternatives:
            continue

        transcript = result.alternatives[0].transcript
        if result.is_final:
            print(f"Original: {transcript}")
            translated_text = translate_text(transcript, target_language=target_language)
            print(f"Translated ({target_language}): {translated_text}")
            text_to_speech(translated_text, language_code=tts_language_code)

def main(input_language='en-US', output_language='ko'):
    config = speech.RecognitionConfig(
        encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
        sample_rate_hertz=RATE,
        language_code=input_language
    )

    streaming_config = speech.StreamingRecognitionConfig(config=config, interim_results=True)

    with MicrophoneStream(RATE, CHUNK) as stream:
        audio_generator = stream.generator()
        requests = (speech.StreamingRecognizeRequest(audio_content=content) for content in audio_generator)
        responses = speech_client.streaming_recognize(streaming_config, requests)
        listen_print_loop(responses, target_language=output_language, tts_language_code=output_language)

def run_application(input_language, output_language):
    print(f"Running with input language: {input_language} and output language: {output_language}")
    main(input_language, output_language)

def gui_main():
    root = tk.Tk()
    root.title("Speech Translation Application")

    languages = ['en-US', 'ko', 'es', 'fr', 'de', 'it', 'ja', 'pt', 'zh']
    language_names = ['English (US)', 'Korean', 'Spanish', 'French', 'German', 'Italian', 'Japanese', 'Portuguese', 'Chinese']
    language_codes = dict(zip(language_names, languages))

    tk.Label(root, text="Select Input Language:").grid(row=0, column=0)
    input_lang_var = tk.StringVar(root)
    input_lang_dropdown = ttk.Combobox(root, textvariable=input_lang_var, values=language_names)
    input_lang_dropdown.grid(row=0, column=1)
    input_lang_dropdown.current(0)

    tk.Label(root, text="Select Output Language:").grid(row=1, column=0)
    output_lang_var = tk.StringVar(root)
    output_lang_dropdown = ttk.Combobox(root, textvariable=output_lang_var, values=language_names)
    output_lang_dropdown.grid(row=1, column=1)
    output_lang_dropdown.current(1)

    def on_start():
        input_lang_code = language_codes[input_lang_var.get()]
        output_lang_code = language_codes[output_lang_var.get()]
        run_application(input_lang_code, output_lang_code)

    start_button = tk.Button(root, text="Start", command=on_start)
    start_button.grid(row=2, column=0, columnspan=2)

    root.mainloop()

if __name__ == '__main__':
    gui_main()

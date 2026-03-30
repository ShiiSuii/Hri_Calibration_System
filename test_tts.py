import pyttsx3
import threading

def speak():
    try:
        e = pyttsx3.init()
        e.say("Hola")
        e.runAndWait()
        print("Done")
    except Exception as e:
        print("Error:", e)

t = threading.Thread(target=speak)
t.start()
t.join()

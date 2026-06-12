from pathlib import Path
import json, os, subprocess, time, wave
import httpx

API_BASE_URL='https://api.elevenlabs.io/v1'
OUTPUT_DIR=Path('backend/runtime/generated/audio/elevenlabs/civilian_extreme_anger_non_gentle')
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_FORMAT='mp3_44100_128'

def load_dotenv():
    for line in Path('.env').read_text(encoding='utf-8').splitlines():
        s=line.strip()
        if s and not s.startswith('#') and '=' in s:
            k,v=s.split('=',1); os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

def dur(path):
    with wave.open(str(path),'rb') as w:
        return w.getnframes()/w.getframerate()

def convert(mp3,wav):
    subprocess.run(['ffmpeg','-y','-i',str(mp3),'-acodec','pcm_s16le','-ac','1','-ar','24000',str(wav)], check=True, capture_output=True, text=True)

def slug(s):
    return ''.join(c.lower() if c.isalnum() else '_' for c in s).strip('_')

load_dotenv()
key=os.getenv('MURPHY_ELEVENLABS_API_KEY') or os.getenv('ELEVENLABS_API_KEY')
model=os.getenv('MURPHY_ELEVENLABS_MODEL_ID','eleven_flash_v2_5')
voices=[
 {'voice_name':'Harry - Fierce Warrior','voice_id':'SOYHLrjzK2X1ezoPC6cr'},
 {'voice_name':'Adam - Dominant, Firm','voice_id':'pNInz6obpgDQGcFmaJgB'},
 {'voice_name':'Callum - Husky Trickster','voice_id':'N2lVS1w4EtoT3dr4eOWO'},
]
samples=[
 {'name':'rage_back_off','text':'Are you kidding me? What the hell is your problem? Back the fuck off. Right now.','settings':{'stability':0.12,'similarity_boost':0.92,'style':1.0,'speed':0.93,'use_speaker_boost':True}},
 {'name':'rage_stop_talking','text':'Shut your mouth. I am not your punching bag. Say one more word like that, and I am calling security.','settings':{'stability':0.16,'similarity_boost':0.9,'style':1.0,'speed':0.88,'use_speaker_boost':True}},
 {'name':'rage_get_out','text':'No. We are done. Get the hell away from me. I do not want to hear another damn word from you.','settings':{'stability':0.18,'similarity_boost':0.9,'style':0.98,'speed':0.86,'use_speaker_boost':True}},
]
results=[]
with httpx.Client(timeout=120) as client:
    for voice in voices:
        for sample in samples:
            start=time.perf_counter()
            base=f"{slug(voice['voice_name'])}_{sample['name']}"
            mp3=OUTPUT_DIR/f'{base}.mp3'
            wav=OUTPUT_DIR/f'{base}.wav'
            r=client.post(f"{API_BASE_URL}/text-to-speech/{voice['voice_id']}", params={'output_format':OUTPUT_FORMAT}, headers={'xi-api-key':key,'Content-Type':'application/json'}, json={'text':sample['text'],'model_id':model,'voice_settings':sample['settings']})
            r.raise_for_status(); mp3.write_bytes(r.content)
            api=time.perf_counter()-start
            cstart=time.perf_counter(); convert(mp3,wav); conv=time.perf_counter()-cstart
            total=time.perf_counter()-start
            item={'voice_name':voice['voice_name'],'voice_id':voice['voice_id'],'name':sample['name'],'text':sample['text'],'settings':sample['settings'],'wav_path':str(wav),'api_seconds':round(api,3),'conversion_seconds':round(conv,3),'total_seconds':round(total,3),'audio_seconds':round(dur(wav),3)}
            results.append(item); print(item)
meta=OUTPUT_DIR/'civilian_extreme_anger_non_gentle_metadata.json'
meta.write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
print({'metadata_path':str(meta)})

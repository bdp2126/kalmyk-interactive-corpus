import os
import shutil
import json
import textgrid
import datetime

# Define folders
TG_DIR = "./textgrids"
AUDIO_DIR = "./audio_files"
OUTPUT_DIR = "./web_corpus"
WEB_AUDIO_DIR = "./web_corpus/audio"

# Ensure all folders exist
os.makedirs(TG_DIR, exist_ok=True)
os.makedirs(AUDIO_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(WEB_AUDIO_DIR, exist_ok=True)

def parse_textgrid(file_path):
    # check if files exist
    try:
        tg = textgrid.TextGrid.fromFile(file_path)
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
        return []
    
    necessary_tiers = ["gloss","orthography","transcription","translation"]
    tier_list = [t.name.casefold() for t in tg.tiers]
    if not set(necessary_tiers).issubset(tier_list):
        result = set(necessary_tiers) - set(tier_list)
        print(f"Missing the following tiers in file {file_path}:\n{''.join(entry+" " for entry in result)}")
        os._exit(0)
    
    # get tiers
    orth_tier = tg.getFirst("Orthography")
    if orth_tier == None:
        orth_tier = tg.getFirst("orthography")
    gloss_tier = tg.getFirst("Gloss")
    if gloss_tier == None:
        gloss_tier = tg.getFirst("gloss")
    ts_tier = tg.getFirst("Transcription")
    if ts_tier == None:
        ts_tier = tg.getFirst("transcription")
    tl_tier = tg.getFirst("Translation")
    if tl_tier == None:
        tl_tier = tg.getFirst("translation")
    
    if not len(ts_tier.intervals) == len(tl_tier.intervals) == len(gloss_tier.intervals) == len(orth_tier.intervals):
        print('Check the length of your tiers!')
        os._exit(0)
    
    aligned_sentences = []
    base_filename = os.path.basename(file_path)
    
    for i in range(len(orth_tier)):
        if orth_tier[i].mark == "":
            continue
        start = orth_tier[i].minTime
        end = orth_tier[i].maxTime
        
        aligned_sentences.append({
            "File": base_filename,
            "AudioFile": base_filename.replace('.TextGrid', '.wav'),
            "Time": f"{datetime.timedelta(seconds=round(start))} - {datetime.timedelta(seconds=round(end))}",
            "StartMs": start*1000,
            "EndMs": end*1000,
            "Orthography": orth_tier[i].mark,
            "Transcription": ts_tier[i].mark,
            "Gloss": gloss_tier[i].mark,
            "Translation": tl_tier[i].mark
        })
    return aligned_sentences

def build_site():
    all_data = []
    files = [f for f in os.listdir(TG_DIR) if f.endswith('.TextGrid')]
    
    if not files:
        print(f"No .TextGrid files found in '{TG_DIR}'. Please drop your Praat files there!")
        os._exit(0)

    # Process textgrids
    for file in files:
        print(f"Processing Text: {file}")
        all_data.extend(parse_textgrid(os.path.join(TG_DIR, file)))

    # Copy audio files to web directory
    audio_files = [f for f in os.listdir(AUDIO_DIR) if f.endswith('.wav')]
    for audio in audio_files:
        print(f"Copying Audio: {audio}")
        shutil.copy2(os.path.join(AUDIO_DIR, audio), os.path.join(WEB_AUDIO_DIR, audio))

    # Write data.js
    with open(os.path.join(OUTPUT_DIR, "data.js"), "w", encoding="utf-8") as f:
        f.write("const corpusData = " + json.dumps(all_data, indent=4, ensure_ascii=False) + ";")

    # Generate index.html (Notice the 'r' before the string to make it a raw string)
    html_content = r"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Interactive Kalmyk Corpus</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script defer src="https://cdn.jsdelivr.net/npm/alpinejs@3.x.x/dist/cdn.min.js"></script>
</head>
<body class="bg-gray-50 text-gray-900 font-sans">

    <script>
        document.addEventListener('alpine:init', () => {
            Alpine.data('corpusApp', () => ({
                activeTab: 'search', // Controls which tab is visible
                search: '', 
                selectedFile: 'all',
                selectedTier: 'all',
                selectedTextType: 'all',
                items: corpusData,
                currentAudioNode: null,
                audioTimeout: null,
                
                get filteredItems() {
                    return this.items.filter(i => {
                        let matchesSearch = true;
                        if (this.search) {
                            const term = this.search.toLowerCase();
                            if (this.selectedTier === 'all') {
                                matchesSearch = (i.Orthography && i.Orthography.toLowerCase().includes(term)) ||
                                                (i.Transcription && i.Transcription.toLowerCase().includes(term)) ||
                                                (i.Gloss && i.Gloss.toLowerCase().includes(term)) ||
                                                (i.Translation && i.Translation.toLowerCase().includes(term));
                            } else {
                                matchesSearch = i[this.selectedTier] && i[this.selectedTier].toLowerCase().includes(term);
                            }
                        }
                        const matchesFile = this.selectedFile === 'all' || i.File === this.selectedFile;
                        const matchesType =
                            this.selectedTextType === 'all' ||
                            (this.selectedTextType === 'spontaneous' && i.File.endsWith('_Spon.TextGrid')) ||
                            (this.selectedTextType === 'read' && i.File.endsWith('_Read.TextGrid')) ||
                            (this.selectedTextType === 'translated' && i.File.endsWith('_Tr.TextGrid'));
                        return matchesSearch && matchesFile && matchesType;
                    });
                },
                get files() {
                    return [...new Set(this.items.map(i => i.File))];
                },
                playAudio(audioFile, startMs, endMs) {
                    let audioEl = document.getElementById('audio-' + audioFile);
                    
                    if (!audioEl) {
                        alert('Audio file ' + audioFile + ' not found! Did you put it in the audio_files folder?');
                        return;
                    }

                    if (this.currentAudioNode) {
                        this.currentAudioNode.pause();
                        clearTimeout(this.audioTimeout);
                    }
                    
                    this.currentAudioNode = audioEl;
                    audioEl.currentTime = startMs / 1000;
                    audioEl.play().catch(e => console.error('Playback error:', e));
                    
                    this.audioTimeout = setTimeout(() => {
                        audioEl.pause();
                    }, endMs - startMs);
                },
                escapeRegExp(string) {
                    return string.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
                },
                highlight(text) {
                    if (!text) return '';
                    if (!this.search.trim()) return text;
                    try {
                        const regex = new RegExp('(' + this.escapeRegExp(this.search) + ')', 'gi');
                        return text.replace(regex, '<mark class="bg-yellow-300 text-gray-900 rounded px-0.5 font-semibold">$1</mark>');
                    } catch(e) {
                        return text;
                    }
                }
            }));
        });
    </script>

    <div class="max-w-7xl mx-auto px-4 py-8" x-data="corpusApp()">
        
        <template x-for="file in files" :key="file">
            <audio :id="'audio-' + file.replace('.TextGrid', '.wav')" :src="'audio/' + file.replace('.TextGrid', '.wav')" preload="auto"></audio>
        </template>

        <div class="border-b border-gray-200 mb-8">
            <nav class="-mb-px flex space-x-8" aria-label="Tabs">
                <button @click="activeTab = 'search'" 
                        :class="activeTab === 'search' ? 'border-indigo-500 text-indigo-600' : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'"
                        class="whitespace-nowrap py-4 px-1 border-b-2 font-medium text-lg transition-colors">
                    Search
                </button>
                <button @click="activeTab = 'about'" 
                        :class="activeTab === 'about' ? 'border-indigo-500 text-indigo-600' : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'"
                        class="whitespace-nowrap py-4 px-1 border-b-2 font-medium text-lg transition-colors">
                    About Us
                </button>
                <button @click="activeTab = 'texts'" 
                        :class="activeTab === 'texts' ? 'border-indigo-500 text-indigo-600' : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'"
                        class="whitespace-nowrap py-4 px-1 border-b-2 font-medium text-lg transition-colors">
                    Collected Texts
                </button>
            </nav>
        </div>

        <div x-show="activeTab === 'search'" x-cloak>
            <div class="bg-white p-4 rounded-xl shadow-sm border border-gray-200 mb-6 flex flex-col md:flex-row gap-4">
                <div class="flex-1">
                    <label class="block text-xs font-semibold uppercase text-gray-500 mb-1">Search Keywords</label>
                    <input type="text" x-model="search" placeholder="Search..." 
                           class="w-full px-4 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500">
                </div>
                
                <div class="w-full md:w-48">
                    <label class="block text-xs font-semibold uppercase text-gray-500 mb-1">Search In</label>
                    <select x-model="selectedTier" class="w-full px-4 py-2 border rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500">
                        <option value="all">All Tiers</option>
                        <option value="Orthography">Orthography</option>
                        <option value="Transcription">Transcription</option>
                        <option value="Gloss">Gloss</option>
                        <option value="Translation">Translation</option>
                    </select>
                </div>

                <div class="w-full md:w-64">
                    <label class="block text-xs font-semibold uppercase text-gray-500 mb-1">Filter by File</label>
                    <select x-model="selectedFile" class="w-full px-4 py-2 border rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500">
                        <option value="all">All Files</option>
                        <template x-for="file in files" :key="file">
                            <option :value="file" x-text="file"></option>
                        </template>
                    </select>
                </div>
                <div class="w-full md:w-48">
                    <label class="block text-xs font-semibold uppercase text-gray-500 mb-1">Text Type</label>
                    <select x-model="selectedTextType" class="w-full px-4 py-2 border rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500">
                        <option value="all">All Types</option>
                        <option value="spontaneous">Spontaneous</option>
                        <option value="read">Read</option>
                        <option value="translated">Translated</option>
                    </select>
                </div>

            </div>

            <div class="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
                <div class="overflow-x-auto">
                    <table class="min-w-full divide-y divide-gray-200 text-left">
                        <thead class="bg-indigo-50 text-indigo-900 font-semibold text-sm">
                            <tr>
                                <th class="px-6 py-4 w-2/12">Metadata & Audio</th>
                                <th class="px-6 py-4 w-10/12">Annotations</th>
                            </tr>
                        </thead>
                        <tbody class="divide-y divide-gray-200 bg-white">
                            <template x-for="item in filteredItems" :key="item.Time + item.Orthography">
                                <tr class="hover:bg-gray-50 transition">
                                    <td class="px-6 py-4 align-top whitespace-nowrap text-xs text-gray-500">
                                        <span class="block font-semibold text-gray-700" x-text="item.File"></span>
                                        
                                        <button @click="playAudio(item.AudioFile, item.StartMs, item.EndMs)"
                                                class="mt-2 bg-indigo-100 hover:bg-indigo-200 text-indigo-700 px-3 py-1.5 rounded-full inline-flex items-center gap-1.5 cursor-pointer transition shadow-sm font-semibold"
                                                title="Click to play audio segment">
                                            <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 20 20"><path d="M10 18a8 8 0 100-16 8 8 0 000 16zM9.555 7.168A1 1 0 008 8v4a1 1 0 001.555.832l3-2a1 1 0 000-1.664l-3-2z" clip-rule="evenodd" fill-rule="evenodd"></path></svg>
                                            <span x-text="item.Time"></span>
                                        </button>
                                    </td>
                                    <td class="px-6 py-4 space-y-2">
                                        <div class="text-lg font-bold text-gray-900" x-html="highlight(item.Orthography)"></div>
                                        <div class="text-sm font-medium text-indigo-700 italic" x-html="highlight(item.Transcription)"></div>
                                        <div class="text-xs font-mono text-gray-500 tracking-wide uppercase bg-gray-55" x-html="highlight(item.Gloss)"></div>
                                        <div class="text-sm text-gray-700 border-l-2 border-indigo-200 pl-3 py-0.5" x-html="highlight(item.Translation)"></div>
                                    </td>
                                </tr>
                            </template>
                        </tbody>
                    </table>
                </div>
                <div x-show="filteredItems.length === 0" class="text-center py-12 text-gray-500">
                    No matches found. Try adjusting your search or tier filter!
                </div>
            </div>
        </div>

        <div x-show="activeTab === 'about'" x-cloak class="bg-white p-8 rounded-xl shadow-sm border border-gray-200">
            <h2 class="text-3xl font-extrabold text-indigo-950 mb-4">About Us</h2>
            <div class="prose max-w-none text-gray-700">
                <p class="mb-4">Welcome to the Interactive Kalmyk Corpus. This project is dedicated to documenting, preserving, and making linguistic data easily searchable.</p>
                <p>Edit this section in the Python script to add information about your research team, project goals, and funding acknowledgments.</p>
            </div>
        </div>

        <div x-show="activeTab === 'texts'" x-cloak class="bg-white p-8 rounded-xl shadow-sm border border-gray-200">
            <h2 class="text-3xl font-extrabold text-indigo-950 mb-6">Collected Texts</h2>
            <p class="text-gray-600 mb-4">The following texts and audio recordings are currently indexed in this corpus:</p>
            
            <ul class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                <template x-for="file in files" :key="file">
                    <li class="bg-gray-50 border border-gray-200 p-4 rounded-lg flex items-center space-x-3">
                        <svg class="w-6 h-6 text-indigo-500 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path></svg>
                        <span x-text="file" class="font-medium text-gray-800 break-all"></span>
                    </li>
                </template>
            </ul>
        </div>

    </div>
    
    <style>
        [x-cloak] { display: none !important; }
    </style>
    <script src="data.js"></script>
</body>
</html>
"""
    with open(os.path.join(OUTPUT_DIR, "index.html"), "w", encoding="utf-8") as f:
        f.write(html_content)

    print(f"\nSuccess! Your interactive web corpus is ready in the '{OUTPUT_DIR}' folder.")

if __name__ == "__main__":
    build_site()

const express = require('express');
const fs = require('fs');
const path = require('path');
const mime = require('mime-types');
const multer = require('multer');

const app = express();
const PORT = process.env.PORT || 3000;
const MEDIA_ROOT = process.env.MEDIA_ROOT || '/media';
const XTREAM_SERVER = (process.env.XTREAM_SERVER || '').replace(/\/$/, '');
const XTREAM_USERNAME = process.env.XTREAM_USERNAME || '';
const XTREAM_PASSWORD = process.env.XTREAM_PASSWORD || '';

const DATA_DIR = path.join(__dirname, 'data');
const STATE_FILE = path.join(DATA_DIR, 'state.json');
const M3U_DIR = path.join(DATA_DIR, 'm3u');

if (!fs.existsSync(DATA_DIR)) fs.mkdirSync(DATA_DIR, { recursive: true });
if (!fs.existsSync(M3U_DIR)) fs.mkdirSync(M3U_DIR, { recursive: true });

function defaultState() {
  return {
    m3uSource: { type: 'url', value: 'https://iptv-org.github.io/iptv/languages/tur.m3u' },
    iptvMode: 'm3u',
    xtreamSection: 'live',
    lastChannel: null,
    mediaPlayerLastPath: '',
    resumeMediaPlayer: null,
    resumeXtream: null
  };
}

function loadState() {
  try {
    const raw = fs.readFileSync(STATE_FILE, 'utf-8');
    return { ...defaultState(), ...JSON.parse(raw) };
  } catch {
    return defaultState();
  }
}

function saveState(state) {
  fs.writeFileSync(STATE_FILE, JSON.stringify(state, null, 2));
}

let state = loadState();

app.use(express.json());
app.use(express.static(path.join(__dirname, 'public')));

function safeResolve(relPath) {
  const root = path.normalize(MEDIA_ROOT);
  const target = path.normalize(path.join(root, relPath || ''));
  if (!target.startsWith(root)) {
    throw new Error('Geçersiz yol');
  }
  return target;
}

// ---- Genel config ----
app.get('/api/config', (req, res) => {
  res.json({
    jellyfinUrl: process.env.JELLYFIN_URL || '',
    xtreamEnabled: !!(XTREAM_SERVER && XTREAM_USERNAME && XTREAM_PASSWORD)
  });
});

// ---- State (kalıcı ayarlar) ----
app.get('/api/state', (req, res) => {
  res.json(state);
});

app.post('/api/state/m3u-mode', (req, res) => {
  state.iptvMode = req.body.mode === 'xtream' ? 'xtream' : 'm3u';
  saveState(state);
  res.json({ ok: true });
});

app.post('/api/state/m3u-url', (req, res) => {
  const url = req.body.url || '';
  state.m3uSource = { type: 'url', value: url };
  saveState(state);
  res.json({ ok: true });
});

const upload = multer({ dest: M3U_DIR });
app.post('/api/state/m3u-file', upload.single('m3ufile'), (req, res) => {
  if (!req.file) return res.status(400).json({ error: 'Dosya yok' });
  const finalPath = path.join(M3U_DIR, 'current.m3u');
  fs.renameSync(req.file.path, finalPath);
  state.m3uSource = { type: 'file', value: 'current.m3u' };
  saveState(state);
  res.json({ ok: true });
});

app.get('/api/m3u-file-content', (req, res) => {
  const filePath = path.join(M3U_DIR, 'current.m3u');
  if (!fs.existsSync(filePath)) return res.status(404).send('');
  res.sendFile(filePath);
});

app.post('/api/state/last-channel', (req, res) => {
  state.lastChannel = { name: req.body.name || '', url: req.body.url || '' };
  saveState(state);
  res.json({ ok: true });
});

app.post('/api/state/xtream-section', (req, res) => {
  state.xtreamSection = req.body.section || 'live';
  saveState(state);
  res.json({ ok: true });
});

app.post('/api/state/mediaplayer-path', (req, res) => {
  state.mediaPlayerLastPath = req.body.path || '';
  saveState(state);
  res.json({ ok: true });
});

app.post('/api/state/resume-mediaplayer', (req, res) => {
  state.resumeMediaPlayer = {
    path: req.body.path,
    position: req.body.position,
    label: req.body.label || req.body.path
  };
  saveState(state);
  res.json({ ok: true });
});

app.post('/api/state/resume-xtream', (req, res) => {
  state.resumeXtream = {
    url: req.body.url,
    position: req.body.position,
    label: req.body.label || ''
  };
  saveState(state);
  res.json({ ok: true });
});

// ---- Media Player: dosya listeleme ----
app.get('/api/files', (req, res) => {
  try {
    const relPath = req.query.path || '';
    const dirPath = safeResolve(relPath);
    const entries = fs.readdirSync(dirPath, { withFileTypes: true });
    const videoExt = ['.mp4', '.mkv', '.avi', '.mov', '.webm', '.m4v', '.ts'];
    const audioExt = ['.mp3', '.flac', '.wav', '.aac', '.m4a', '.ogg'];

    const items = entries
      .filter(e => !e.name.startsWith('.'))
      .map(e => {
        const ext = path.extname(e.name).toLowerCase();
        let type = 'other';
        if (e.isDirectory()) type = 'folder';
        else if (videoExt.includes(ext)) type = 'video';
        else if (audioExt.includes(ext)) type = 'audio';
        return { name: e.name, type, path: path.posix.join(relPath, e.name) };
      })
      .sort((a, b) => {
        if (a.type === 'folder' && b.type !== 'folder') return -1;
        if (a.type !== 'folder' && b.type === 'folder') return 1;
        return a.name.localeCompare(b.name, 'tr');
      });

    res.json({ path: relPath, items });
  } catch (err) {
    res.status(400).json({ error: err.message });
  }
});

app.get('/stream', (req, res) => {
  try {
    const relPath = req.query.path || '';
    const filePath = safeResolve(relPath);
    const stat = fs.statSync(filePath);
    const fileSize = stat.size;
    const range = req.headers.range;
    const contentType = mime.lookup(filePath) || 'application/octet-stream';

    if (range) {
      const parts = range.replace(/bytes=/, '').split('-');
      const start = parseInt(parts[0], 10);
      const end = parts[1] ? parseInt(parts[1], 10) : fileSize - 1;
      const chunkSize = (end - start) + 1;
      const stream = fs.createReadStream(filePath, { start, end });
      res.writeHead(206, {
        'Content-Range': `bytes ${start}-${end}/${fileSize}`,
        'Accept-Ranges': 'bytes',
        'Content-Length': chunkSize,
        'Content-Type': contentType
      });
      stream.pipe(res);
    } else {
      res.writeHead(200, {
        'Content-Length': fileSize,
        'Content-Type': contentType,
        'Accept-Ranges': 'bytes'
      });
      fs.createReadStream(filePath).pipe(res);
    }
  } catch (err) {
    res.status(404).send('Dosya bulunamadı');
  }
});

// ---- Xtream Codes proxy ----
function xtreamCheck(res) {
  if (!XTREAM_SERVER || !XTREAM_USERNAME || !XTREAM_PASSWORD) {
    res.status(400).json({ error: 'Xtream ayarları tanımlı değil' });
    return false;
  }
  return true;
}

async function xtreamApi(action, extraParams) {
  const params = new URLSearchParams({
    username: XTREAM_USERNAME,
    password: XTREAM_PASSWORD,
    action
  });
  if (extraParams) {
    Object.keys(extraParams).forEach(k => params.append(k, extraParams[k]));
  }
  const url = `${XTREAM_SERVER}/player_api.php?${params.toString()}`;
  const r = await fetch(url);
  if (!r.ok) throw new Error('Xtream sunucusu yanıt vermedi: ' + r.status);
  return r.json();
}

app.get('/api/xtream/categories', async (req, res) => {
  if (!xtreamCheck(res)) return;
  try {
    const type = req.query.type;
    const actionMap = {
      live: 'get_live_categories',
      vod: 'get_vod_categories',
      series: 'get_series_categories'
    };
    const action = actionMap[type];
    if (!action) return res.status(400).json({ error: 'Geçersiz tip' });
    const data = await xtreamApi(action);
    res.json(data);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.get('/api/xtream/streams', async (req, res) => {
  if (!xtreamCheck(res)) return;
  try {
    const type = req.query.type;
    const categoryId = req.query.category_id;
    const actionMap = { live: 'get_live_streams', vod: 'get_vod_streams' };
    const action = actionMap[type];
    if (!action) return res.status(400).json({ error: 'Geçersiz tip' });
    const data = await xtreamApi(action, { category_id: categoryId });

    const items = data.map(item => {
      let url = '';
      if (type === 'live') {
        url = `${XTREAM_SERVER}/live/${XTREAM_USERNAME}/${XTREAM_PASSWORD}/${item.stream_id}.m3u8`;
      } else {
        const ext = item.container_extension || 'mp4';
        url = `${XTREAM_SERVER}/movie/${XTREAM_USERNAME}/${XTREAM_PASSWORD}/${item.stream_id}.${ext}`;
      }
      return {
        id: item.stream_id,
        name: item.name,
        icon: item.stream_icon || '',
        url
      };
    });
    res.json(items);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.get('/api/xtream/series', async (req, res) => {
  if (!xtreamCheck(res)) return;
  try {
    const categoryId = req.query.category_id;
    const data = await xtreamApi('get_series', { category_id: categoryId });
    const items = data.map(item => ({
      id: item.series_id,
      name: item.name,
      icon: item.cover || ''
    }));
    res.json(items);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.get('/api/xtream/series-info', async (req, res) => {
  if (!xtreamCheck(res)) return;
  try {
    const seriesId = req.query.series_id;
    const data = await xtreamApi('get_series_info', { series_id: seriesId });
    const episodes = [];
    const seasons = data.episodes || {};
    Object.keys(seasons).forEach(seasonNum => {
      seasons[seasonNum].forEach(ep => {
        const ext = ep.container_extension || 'mp4';
        episodes.push({
          season: seasonNum,
          episodeNum: ep.episode_num,
          title: ep.title || `Bölüm ${ep.episode_num}`,
          url: `${XTREAM_SERVER}/series/${XTREAM_USERNAME}/${XTREAM_PASSWORD}/${ep.id}.${ext}`
        });
      });
    });
    res.json({ info: data.info || {}, episodes });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.listen(PORT, () => {
  console.log(`Tesla Player ${PORT} portunda çalışıyor, medya kökü: ${MEDIA_ROOT}`);
});

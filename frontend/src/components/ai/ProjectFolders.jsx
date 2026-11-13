import { useEffect, useState } from 'react';
import api from '../../services/api';
import { getGeneratedImage } from '../../services/aiService';
import { getOwnerGeneratedImage } from '../../services/ownerAiService';

export function phaseLabel(generation) {
  return generation.phase_number ? `Phase ${generation.phase_number}` : `${generation.status === "completed" ? "Legacy batch" : "Generation"} #${generation.id}`;
}

export function useProjectGallery(refresh) {
  const [folders, setFolders] = useState([]), [selected, setSelected] = useState(null);
  const [items, setItems] = useState([]), [cursor, setCursor] = useState(null);
  const [error, setError] = useState(''), [loading, setLoading] = useState(true);
  const [page, setPage] = useState(null);
  useEffect(() => { setPage(null); }, [refresh]);
  useEffect(() => {
    const controller = new AbortController();
    setLoading(true); setError('');
    const url = selected ? `/ai/gallery/folders/${selected.key}` : '/ai/gallery/folders';
    api.get(url, { signal: controller.signal, params: { before: page } }).then(({data}) => {
      if (controller.signal.aborted) return;
      if (selected) { setItems(current => page ? [...current, ...data.items] : data.items); setCursor(data.next_before); }
      else { setFolders(data); setItems([]); setCursor(null); }
    }).catch(e => { if (!controller.signal.aborted) setError(e.response?.data?.detail || 'Unable to load gallery. Please retry.'); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [selected, page, refresh]);
  return {folders, selected, items, setItems, error, setError, loading,
    open: folder => { setItems([]); setPage(null); setCursor(null); setSelected(folder); },
    hasMore: !!cursor, loadMore: () => setPage(cursor)};
}

function Folder({folder, owner, onOpen}) {
  const [url, setUrl] = useState('');
  useEffect(() => {
    const controller = new AbortController(); let objectUrl;
    setUrl('');
    if (folder.cover_id) (owner ? getOwnerGeneratedImage : getGeneratedImage)(folder.cover_id, controller.signal)
      .then(blob => { if (!controller.signal.aborted) { objectUrl = URL.createObjectURL(blob); setUrl(objectUrl); } }).catch(() => {});
    return () => { controller.abort(); if (objectUrl) URL.revokeObjectURL(objectUrl); };
  }, [folder.cover_id, owner]);
  return <button type="button" className="account-card gallery-folder" onClick={() => onOpen(folder)}>
    {url ? <img src={url} alt="" /> : <span className="gallery-folder-placeholder" aria-hidden="true">▱</span>}
    <strong>{folder.name}</strong><span>{folder.image_count} images</span>
  </button>;
}

export default function ProjectFolders({gallery, owner=false}) {
  if (gallery.selected) return <div className="account-heading"><button className="account-secondary" onClick={() => gallery.open(null)}>Back to folders</button><h2>{gallery.selected.name}</h2></div>;
  return <div className="ai-image-grid">{gallery.folders.map(folder => <Folder key={folder.key} folder={folder} owner={owner} onOpen={gallery.open} />)}</div>;
}

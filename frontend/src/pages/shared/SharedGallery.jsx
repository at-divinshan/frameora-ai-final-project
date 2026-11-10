import { useCallback, useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import ImageComments from '../../components/ai/ImageComments';
import AccountLayout from '../../components/layout/AccountLayout';
import GeneratedImageCard from '../../components/ai/GeneratedImageCard';
import { getSharedGallery, getSharedImage, sharingError } from '../../services/shareService';
import '../../styles/ai.css';

export default function SharedGallery() {
  const { token } = useParams();
  const [data, setData] = useState(null), [error, setError] = useState('');
  const [revision, setRevision] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    setData(null); setError('');
    getSharedGallery(token, controller.signal).then(result => { if (!controller.signal.aborted) setData(result); })
      .catch(e => { if (!controller.signal.aborted) setError(sharingError(e)); });
    return () => controller.abort();
  }, [token, revision]);
  useEffect(() => {
    const refresh = () => setRevision(n => n + 1);
    window.addEventListener('focus', refresh);
    return () => window.removeEventListener('focus', refresh);
  }, []);
  const loadImage = useCallback((id, signal) => getSharedImage(token, id, signal), [token]);
  return <AccountLayout><section className="ai-page"><header className="account-heading"><div><h1>Shared Photography Gallery</h1><p>Photography concepts shared with you by the studio.</p></div></header>
    {!data && !error && <p role="status">Loading shared gallery…</p>}
    {error && <div className="account-error" role="alert">{error}<button className="account-secondary" onClick={() => setRevision(n => n + 1)}>Retry</button></div>}
    {data && (data.images.length ? <div className="ai-image-grid">{data.images.map((image, index) => <div key={image.id}><GeneratedImageCard image={image} index={index} loadImage={loadImage} allowDownload={false} /><ImageComments token={token} imageId={image.id} /></div>)}</div> : <p>No images are available in this shared gallery.</p>)}
  </section></AccountLayout>;
}

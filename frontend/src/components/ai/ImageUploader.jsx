import { useEffect, useRef, useState } from 'react';
export default function ImageUploader({ onChange, disabled, value, id = 'reference', background = false }) {
  const input = useRef(null);
  const [localFile, setLocalFile] = useState(null);
  const [preview, setPreview] = useState(null);
  const [error, setError] = useState('');
  const file = value === undefined ? localFile : value;
  useEffect(() => {
    if (!file) { setPreview(null); if (input.current) input.current.value = ''; return; }
    const url = URL.createObjectURL(file); setPreview(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);
  function change(next) {
    if (next && (next.size > 5 * 1024 * 1024 || !['image/jpeg','image/png','image/webp'].includes(next.type))) {
      setError('Choose a JPEG, PNG or WebP image of at most 5 MiB.');
      if (input.current) input.current.value = '';
      return;
    }
    setError(''); setLocalFile(next); onChange(next);
  }
  return <div className="form-field"><label htmlFor={id}>{background ? 'Background Reference Image' : 'Person Reference Image'} (optional)</label>
    <input ref={input} id={id} type="file" accept="image/jpeg,image/png,image/webp" disabled={disabled} onChange={event => change(event.target.files?.[0] || null)} />
    <small>JPEG, PNG or WebP, up to 5 MiB. {background ? 'Guides the scene; exact background reproduction is not guaranteed.' : 'A clear photo helps guide appearance; exact facial consistency is not guaranteed.'}</small>
    {error && <p role="alert">{error}</p>}
    {preview && <img src={preview} alt={background ? 'Background reference preview' : 'Person reference preview'} style={{display:'block',maxWidth:'100%',width:240,maxHeight:160,objectFit:'contain'}} />}
    {file && <button type="button" className="account-secondary" disabled={disabled} onClick={()=>change(null)}>Remove {background ? 'background' : 'person'} image</button>}
  </div>;
}

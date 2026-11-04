import { useEffect, useState } from "react";
import { getGeneratedImage } from "../../services/aiService";

export default function GeneratedImageCard({ image, index }) {
  const [url, setUrl] = useState("");
  const [error, setError] = useState(false);
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    let objectUrl;
    setUrl(""); setError(false);
    getGeneratedImage(image.id, controller.signal).then((blob) => {
      if (controller.signal.aborted) return;
      objectUrl = URL.createObjectURL(blob);
      setUrl(objectUrl);
    }).catch(() => { if (!controller.signal.aborted) setError(true); });
    return () => { controller.abort(); if (objectUrl) URL.revokeObjectURL(objectUrl); };
  }, [image.id, attempt]);
  return <figure className="ai-image-card">
    {url ? <><img src={url} alt={`Generated photography pose ${index + 1}`} /><figcaption>Pose {index + 1} <a href={url} download={`frameora-${image.id}.png`}>Download</a></figcaption></> : error ? <p role="alert">Image could not load. <button type="button" onClick={() => setAttempt(attempt + 1)}>Retry</button></p> : <p role="status">Loading image…</p>}
  </figure>;
}

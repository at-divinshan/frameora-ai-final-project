import { useEffect, useRef, useState } from "react";
import { getGeneratedImage } from "../../services/aiService";

export default function GeneratedImageCard({ image, index, loadImage = getGeneratedImage, enablePreview = false }) {
  const preview = useRef(null);
  const [url, setUrl] = useState("");
  const [error, setError] = useState(false);
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    let objectUrl;
    setUrl(""); setError(false);
    loadImage(image.id, controller.signal).then((blob) => {
      if (controller.signal.aborted) return;
      objectUrl = URL.createObjectURL(blob);
      setUrl(objectUrl);
    }).catch(() => { if (!controller.signal.aborted) setError(true); });
    return () => { controller.abort(); if (objectUrl) URL.revokeObjectURL(objectUrl); };
  }, [image.id, attempt, loadImage]);
  const setup = image.guidance?.camera_setup;
  return <figure className="ai-image-card">
    {url ? enablePreview ? <><button className="owner-image-preview" type="button" onClick={() => preview.current?.showModal()} aria-label={`Preview image ${index + 1}`}><img src={url} alt={`Generated photography concept ${index + 1}`} /><span>Preview image</span></button>
      <dialog ref={preview} className="owner-image-dialog" aria-label={`Image ${index + 1} preview`} onClick={event => { if (event.target === event.currentTarget) preview.current.close(); }}><button autoFocus className="account-secondary" type="button" onClick={() => preview.current.close()}>Close preview</button><img src={url} alt={`Generated photography concept ${index + 1}`} /></dialog></> : <img src={url} alt={`Generated photography concept ${index + 1}`} /> : error ? <p role="alert">Image could not load. <button type="button" onClick={() => setAttempt(attempt + 1)}>Retry</button></p> : <p role="status">Loading image…</p>}
    <figcaption>
      <div className="ai-image-heading"><h3>{image.guidance?.pose_name || `Image ${index + 1}`}</h3>
      </div>
      {image.guidance ? <>
        <dl className="user-plan-preference-list">
          <div><dt>Camera angle</dt><dd>{image.guidance.camera_angle}</dd></div>
          {setup && <div><dt>Camera distance</dt><dd>{setup.camera_distance}</dd></div>}
          <div><dt>Shot type</dt><dd>{image.guidance.shot_type}</dd></div>
          <div><dt>Camera position</dt><dd>{image.guidance.camera_position}</dd></div>
        </dl>
        {setup ? <details className="ai-camera-guide">
          <summary>Camera Setup Guide <span>{setup.steps.length} practical steps</span></summary>
          <dl className="user-plan-preference-list">
            {[
              ["Camera height", setup.camera_height],
              ["Camera direction and tilt", setup.camera_direction_and_tilt],
              ["Suggested lens or smartphone zoom", setup.suggested_lens_or_zoom],
              ["Lighting direction", setup.lighting_direction],
              ["Subject position", setup.subject_position],
            ].map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}
          </dl>
          <ol>{setup.steps.map((step, stepIndex) => <li key={stepIndex}>{step}</li>)}</ol>
        </details> : <>
          <p>{image.guidance.instructions}</p>
          <p className="ai-note">A detailed camera setup guide was not saved for this older image.</p>
        </>}
        <p className="ai-note">Planned photography guidance used for generation. The image has not been visually verified.</p>
      </> : <p className="ai-note">Photography guidance was not saved for this older image.</p>}
      {url && <a className="user-dashboard-create-button ai-download" href={url} download={`frameora-${image.id}.png`}>Download Image</a>}
    </figcaption>
  </figure>;
}

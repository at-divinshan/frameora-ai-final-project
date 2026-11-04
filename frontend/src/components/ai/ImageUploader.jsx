export default function ImageUploader({ onChange, disabled }) {
  return <div className="form-field"><label htmlFor="reference">Reference photo (optional)</label>
    <input id="reference" type="file" accept="image/jpeg,image/png,image/webp" disabled={disabled} onChange={(event) => onChange(event.target.files?.[0] || null)} />
    <small>JPEG, PNG or WebP, up to 5 MiB. A clear photo helps keep facial appearance consistent.</small>
  </div>;
}

import { LoaderCircle } from "lucide-react";

export default function GenerationLoader({ imageCount = 4, message }) {
  const statusMessage = message ??
    (imageCount === 4
      ? "This can take several minutes. Your free request is used only when all four images are saved."
      : `This can take several minutes. The batch is complete only when all ${imageCount} images are saved.`);
  return <section className="ai-generation-loader" aria-busy="true" aria-label="Generating images">
    <div className="ai-loading-status" role="status" aria-live="polite">
      <LoaderCircle className="ai-spinner" size={24} aria-hidden="true" />
      <div><strong>Creating {imageCount} photography concepts…</strong><p>{statusMessage}</p></div>
    </div>
    <div className="ai-image-grid" aria-hidden="true">
      {Array.from({ length: imageCount }, (_, index) => <div className="ai-image-card ai-skeleton-card" key={index}>
        <div className="ai-skeleton ai-skeleton-preview" /><div className="ai-skeleton-copy"><div className="ai-skeleton" /><div className="ai-skeleton" /></div>
      </div>)}
    </div>
  </section>;
}

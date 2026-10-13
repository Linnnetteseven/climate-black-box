/**
 * A full-bleed chapter heading between evidence sections.
 *
 * This exists to fix a specific problem: the cinematic opening and the
 * evidence below it read as two different products. The opening is full-bleed
 * imagery and 60px display type; the evidence was a narrow column of small
 * cards. Nothing carried the eye across the seam.
 *
 * A chapter band carries the same language -- edge-to-edge, display type, a
 * number, optional imagery -- but it is deliberately short (about half a
 * viewport, not a full one) so it gives rhythm without making a presenter
 * scroll through another screen of atmosphere to reach the thing they came to
 * show.
 */

export function Chapter({
  index, title, lede, image, tone = "plain", ambience, tall = false,
}: {
  index: string;
  title: string;
  lede?: string;
  image?: string;
  tone?: "plain" | "image";
  /** Switches the ambient bed while this band is on screen. */
  ambience?: "space" | "forest";
  /** Full-height, for a band whose imagery is the point. */
  tall?: boolean;
}) {
  const hasImage = tone === "image" && image;

  return (
    <section
      data-ambience={ambience}
      style={{
        position: "relative",
        margin: "0 calc(50% - 50vw)",
        width: "100vw",
        minHeight: hasImage ? (tall ? "92vh" : "52vh") : "auto",
        display: "flex",
        alignItems: "center",
        overflow: "hidden",
        // No rules. A hard line across the page is what made the lower half
        // read as a stack of boxes while the opening read as one continuous
        // scene; the imagery fades out at its own edges instead.
        padding: hasImage ? "0" : "72px 0 8px",
      }}
    >
      {hasImage && (
        <>
          <img
            src={image}
            alt=""
            aria-hidden
            decoding="async"
            style={{
              position: "absolute", inset: 0, width: "100%", height: "100%",
              objectFit: "cover", opacity: 0.5,
              // Dissolve into the page at top and bottom rather than stopping
              // at a line.
              maskImage:
                "linear-gradient(to bottom, transparent 0%, #000 22%, #000 78%, transparent 100%)",
              WebkitMaskImage:
                "linear-gradient(to bottom, transparent 0%, #000 22%, #000 78%, transparent 100%)",
            }}
          />
          <div
            aria-hidden
            style={{
              position: "absolute", inset: 0,
              background:
                "linear-gradient(to right, rgba(10,20,24,0.94) 0%, rgba(10,20,24,0.68) 48%, rgba(10,20,24,0.30) 100%)",
            }}
          />
        </>
      )}

      <div
        style={{
          position: "relative", width: "100%", maxWidth: 1120,
          margin: "0 auto", padding: "0 24px",
        }}
      >
        <div
          className="mono"
          style={{
            fontSize: 11, letterSpacing: "0.22em", textTransform: "uppercase",
            color: "var(--series-ndvi)", marginBottom: 14,
          }}
        >
          {index}
        </div>
        <h2
          style={{
            fontFamily: "var(--font-display)", fontWeight: 700,
            fontSize: "clamp(28px, 4.4vw, 54px)", lineHeight: 1.03,
            letterSpacing: "-0.03em", margin: 0, maxWidth: "17ch",
          }}
        >
          {title}
        </h2>
        {lede && (
          <p
            style={{
              fontSize: "clamp(15px, 1.4vw, 19px)", color: "var(--ink-2)",
              maxWidth: "52ch", marginTop: 16, lineHeight: 1.55,
            }}
          >
            {lede}
          </p>
        )}
      </div>
    </section>
  );
}

"use client";
import { useEffect, useState } from "react";
import type { MatchCard } from "@/lib/api";
export function LocalKickoff({match}: {match: MatchCard}) {
  const [now, setNow] = useState<number | null>(null);
  useEffect(() => { setNow(Date.now()); const id = setInterval(() => setNow(Date.now()), 30_000); return () => clearInterval(id); }, []);
  if (match.status === "SCHEDULED") return <span>Kickoff time not confirmed · {match.utc_date.slice(0, 10)}</span>;
  const remaining = now === null ? null : new Date(match.utc_date).getTime() - now;
  return <span><time dateTime={match.utc_date}>{now === null ? match.utc_date : new Date(match.utc_date).toLocaleString(undefined, {dateStyle: "medium", timeStyle: "short"})}</time>
    {now !== null && " · Your local time"}
    {match.status === "TIMED" && remaining !== null && remaining > 0 && ` · In ${Math.floor(remaining / 86400000)}d ${Math.floor(remaining / 3600000) % 24}h ${Math.floor(remaining / 60000) % 60}m`}
  </span>;
}

export function ShareCard({title, lines, updated}: {title: string; lines: string[]; updated: string | null}) {
  const [message, setMessage] = useState("");
  async function create(share: boolean) {
    try {
      const canvas = document.createElement("canvas"); canvas.width = 1080; canvas.height = 1350;
      const ctx = canvas.getContext("2d"); if (!ctx) throw new Error();
      ctx.fillStyle = "#101b36"; ctx.fillRect(0, 0, 1080, 1350);
      ctx.fillStyle = "#c9a85d"; ctx.fillRect(70, 160, 940, 5);
      try {
        const logo = new Image(); logo.src = "/logo.png";
        await logo.decode(); ctx.drawImage(logo, 70, 55, 70, 70);
      } catch { /* Wordmark remains present when the image cannot load. */ }
      ctx.font = "bold 40px Georgia"; ctx.fillText("ECHO MADRID", 160, 110);
      ctx.fillStyle = "white"; ctx.font = "bold 56px Georgia";
      const wrap = (text: string, y: number, size: number) => {
        ctx.font = `${size}px Georgia`;
        let line = "";
        for (const word of text.split(" ")) {
          if (ctx.measureText(line + word).width > 920) { ctx.fillText(line, 80, y); y += size * 1.4; line = ""; }
          line += word + " ";
        }
        ctx.fillText(line, 80, y); return y + size * 1.6;
      };
      let y = wrap(title, 270, 56);
      for (const line of lines.slice(0, 8)) y = wrap(line, y + 20, 34);
      ctx.fillStyle = "#c9a85d";
      wrap("football-data.org · Stored snapshot, not live scores", 1190, 25);
      wrap(`Imported: ${updated || "unknown — freshness unverified"}`, 1240, 23);
      const blob = await new Promise<Blob>((resolve, reject) => canvas.toBlob(b => b ? resolve(b) : reject(), "image/png"));
      const file = new File([blob], "echo-madrid-card.png", {type: "image/png"});
      if (share && navigator.canShare?.({files: [file]})) { await navigator.share({files: [file], title}); return; }
      const url = URL.createObjectURL(blob); const a = document.createElement("a");
      a.href = url; a.download = file.name; a.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
      setMessage("Card downloaded.");
    } catch (error) { if (!(error instanceof DOMException && error.name === "AbortError")) setMessage("Could not create the card. Please try downloading again."); }
  }
  return <div className="card-actions"><button className="refresh-button" onClick={() => create(false)}>Download card</button><button className="refresh-button" onClick={() => create(true)}>Share card</button><span role="status">{message}</span></div>;
}

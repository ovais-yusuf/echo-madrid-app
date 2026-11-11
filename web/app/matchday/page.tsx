import { MatchdayPanel } from "@/components/matchday-panel";
export const dynamic = "force-dynamic";
export default function MatchdayPage() {
  return <div className="page-container"><section className="page-hero"><div className="hero-copy"><span className="eyebrow">ECHO MADRID / MATCHDAY</span><h1>The next<br/><span>chapter.</span></h1><p>Provider-reported match states, grounded previews and shareable cards.</p></div></section><MatchdayPanel/></div>;
}

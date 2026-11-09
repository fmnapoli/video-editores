import React from 'react';
import {AbsoluteFill, Sequence, interpolate, spring, useCurrentFrame, useVideoConfig, random} from 'remotion';
import {createTikTokStyleCaptions, type Caption} from '@remotion/captions';
import {TransitionSeries, linearTiming} from '@remotion/transitions';
import {wipe} from '@remotion/transitions/wipe';

export type DemoProps = {titulo: string; sub: string; captions: Caption[]};
const FONTE = 'Inter, "DejaVu Sans", sans-serif';

const Fundo: React.FC<{cor: string}> = ({cor}) => {
  const pontos = new Array(40).fill(0).map((_, i) => ({x: random(`x${i}`) * 1920, y: random(`y${i}`) * 1080, r: 2 + random(`r${i}`) * 4}));
  return (
    <AbsoluteFill style={{background: `radial-gradient(ellipse at 30% 20%, ${cor}, #0f172a 70%)`}}>
      <svg width={1920} height={1080}>{pontos.map((p, i) => <circle key={i} cx={p.x} cy={p.y} r={p.r} fill="white" opacity={0.08} />)}</svg>
    </AbsoluteFill>
  );
};

const Titulo: React.FC<{titulo: string; sub: string}> = ({titulo, sub}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const s = spring({frame, fps, config: {damping: 14, stiffness: 120}});
  const op = interpolate(frame, [0, 12], [0, 1], {extrapolateRight: 'clamp'});
  return (
    <AbsoluteFill style={{justifyContent: 'center', alignItems: 'center', fontFamily: FONTE, color: 'white'}}>
      <div style={{transform: `scale(${0.8 + 0.2 * s})`, opacity: op, fontSize: 110, fontWeight: 800, letterSpacing: -2}}>{titulo}</div>
      <div style={{opacity: interpolate(frame, [10, 25], [0, 1], {extrapolateRight: 'clamp'}), fontSize: 44, marginTop: 20, color: '#93c5fd'}}>{sub}</div>
    </AbsoluteFill>
  );
};

const LowerThird: React.FC = () => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const x = spring({frame, fps, from: -600, to: 0, config: {damping: 18}});
  return (
    <div style={{position: 'absolute', left: 80, bottom: 320, transform: `translateX(${x}px)`, background: 'rgba(15,23,42,0.75)', borderLeft: '10px solid #2563EB', padding: '18px 36px', color: 'white', fontFamily: FONTE}}>
      <div style={{fontSize: 46, fontWeight: 700}}>Alessandro "Primata"</div>
      <div style={{fontSize: 30, color: '#cbd5e1'}}>Professor de bateria · Taubaté</div>
    </div>
  );
};

const Legendas: React.FC<{captions: Caption[]}> = ({captions}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const t = (frame / fps) * 1000;
  const {pages} = createTikTokStyleCaptions({captions, combineTokensWithinMilliseconds: 1400});
  const pag = pages.find((p) => t >= p.startMs && t < p.startMs + p.durationMs);
  if (!pag) return null;
  return (
    <AbsoluteFill style={{justifyContent: 'flex-end', alignItems: 'center', paddingBottom: 90}}>
      <div style={{fontFamily: FONTE, fontSize: 56, fontWeight: 700, color: 'white', background: 'rgba(0,0,0,0.55)', padding: '12px 28px', borderRadius: 14, maxWidth: 1500, textAlign: 'center'}}>
        {pag.tokens.map((tok, i) => <span key={i} style={{color: t >= tok.fromMs && t < tok.toMs ? '#facc15' : 'white'}}>{tok.text}</span>)}
      </div>
    </AbsoluteFill>
  );
};

export const Demo: React.FC<DemoProps> = ({titulo, sub, captions}) => {
  const {durationInFrames} = useVideoConfig();
  return (
    <AbsoluteFill>
      <TransitionSeries>
        <TransitionSeries.Sequence durationInFrames={60}>
          <Fundo cor="#1e3a8a" />
          <Titulo titulo={titulo} sub={sub} />
        </TransitionSeries.Sequence>
        <TransitionSeries.Transition presentation={wipe({direction: 'from-left'})} timing={linearTiming({durationInFrames: 15})} />
        <TransitionSeries.Sequence durationInFrames={Math.max(30, durationInFrames - 60)}>
          <Fundo cor="#7c2d12" />
          <LowerThird />
        </TransitionSeries.Sequence>
      </TransitionSeries>
      <Sequence from={0}><Legendas captions={captions} /></Sequence>
    </AbsoluteFill>
  );
};

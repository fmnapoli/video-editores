import React from 'react';
import {AbsoluteFill, OffthreadVideo, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {createTikTokStyleCaptions, type Caption} from '@remotion/captions';

export const Burn: React.FC<{captions: Caption[]}> = ({captions}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const t = (frame / fps) * 1000;
  const {pages} = createTikTokStyleCaptions({captions, combineTokensWithinMilliseconds: 1400});
  const pag = pages.find((p) => t >= p.startMs && t < p.startMs + p.durationMs);
  return (
    <AbsoluteFill>
      <OffthreadVideo src={staticFile('seg.mp4')} />
      {pag && (
        <AbsoluteFill style={{justifyContent: 'flex-end', alignItems: 'center', paddingBottom: 90}}>
          <div style={{fontFamily: 'Inter, sans-serif', fontSize: 56, fontWeight: 700, color: 'white', background: 'rgba(0,0,0,0.55)', padding: '12px 28px', borderRadius: 14}}>
            {pag.tokens.map((tok, i) => <span key={i} style={{color: t >= tok.fromMs && t < tok.toMs ? '#facc15' : 'white'}}>{tok.text}</span>)}
          </div>
        </AbsoluteFill>
      )}
    </AbsoluteFill>
  );
};

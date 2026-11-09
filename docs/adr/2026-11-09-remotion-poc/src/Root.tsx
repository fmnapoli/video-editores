import {Composition, staticFile} from 'remotion';
import {parseSrt, type Caption} from '@remotion/captions';
import {Demo, type DemoProps} from './Demo';
import {Burn} from './Burn';

// Convenção do @remotion/captions: o espaço INICIAL do texto separa as palavras.
// Um SRT com um cue por palavra não traz esse espaço; sem ele, createTikTokStyleCaptions()
// junta todas as palavras numa página só.
const comEspaco = (cs: Caption[]) => cs.map((c) => ({...c, text: c.text.startsWith(' ') ? c.text : ' ' + c.text}));

export const Root = () => (
  <>
    <Composition
      id="Demo"
      component={Demo}
      width={1920}
      height={1080}
      fps={30}
      durationInFrames={30 * 8}
      defaultProps={{titulo: 'Como ler a partitura', sub: 'Curso de bateria · Cap. 1', captions: []} as DemoProps}
      calculateMetadata={async ({props}) => {
        const srt = await fetch(staticFile('trecho.srt')).then((r) => r.text());
        const captions = comEspaco(parseSrt({input: srt}).captions);
        const fim = Math.max(...captions.map((c) => c.endMs));
        return {props: {...props, captions}, durationInFrames: Math.ceil((fim / 1000) * 30) + 15};
      }}
    />
    {/* Queima de legenda sobre filmagem: public/seg.mp4 (60 s, 1080p30) + public/seg.srt por palavra. */}
    <Composition
      id="Burn"
      component={Burn}
      width={1920}
      height={1080}
      fps={30}
      durationInFrames={1800}
      defaultProps={{captions: [] as Caption[]}}
      calculateMetadata={async ({props}) => {
        const srt = await fetch(staticFile('seg.srt')).then((r) => r.text());
        return {props: {...props, captions: comEspaco(parseSrt({input: srt}).captions)}};
      }}
    />
  </>
);

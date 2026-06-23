'use client';

import { useMemo } from 'react';
import { brandName } from '@/lib/platform';

export function SecureDocumentPreview({ customerName, type = 'pdf' }: { customerName: string; type?: 'pdf' | 'image' }) {
  const today = useMemo(() => new Date().toLocaleDateString('en-IN'), []);
  const watermark = `PREVIEW ONLY • ${brandName} • ${customerName} • ${today}`;

  return (
    <section
      className="safe-preview relative overflow-hidden rounded-[2rem] border border-white/15 bg-slate-950/80 p-6"
      onContextMenu={(event) => event.preventDefault()}
      draggable={false}
      aria-label="Protected low-resolution preview"
    >
      <div className="absolute inset-0 z-20 grid rotate-[-24deg] select-none grid-cols-2 gap-8 opacity-20 pointer-events-none">
        {Array.from({ length: 16 }).map((_, index) => <span key={index} className="text-xl font-black text-white">{watermark}</span>)}
      </div>
      <div className="relative z-10 min-h-[420px] rounded-3xl border border-dashed border-emerald/40 bg-gradient-to-br from-white/15 to-white/5 p-8 blur-[.15px]">
        <div className="mb-6 flex items-center justify-between text-sm text-white/60">
          <span>{type === 'pdf' ? 'PDF toolbar disabled' : 'Image save and drag disabled'}</span>
          <span>Signed preview token expires in 5 minutes</span>
        </div>
        <div className="space-y-4">
          <div className="h-8 w-2/3 rounded-full bg-white/30" />
          <div className="h-4 w-full rounded-full bg-white/20" />
          <div className="h-4 w-11/12 rounded-full bg-white/20" />
          <div className="h-4 w-10/12 rounded-full bg-white/20" />
          <div className="mt-10 grid grid-cols-2 gap-4">
            <div className="h-40 rounded-2xl bg-royal/20" />
            <div className="h-40 rounded-2xl bg-emerald/20" />
          </div>
        </div>
      </div>
    </section>
  );
}

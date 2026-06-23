import { LockKeyhole, Sparkles, Shield, DownloadCloud } from 'lucide-react';
import { SecureDocumentPreview } from '@/components/document-preview';
import { brandName, documentCategories, metrics, modules, productName, roles } from '@/lib/platform';

export default function Home() {
  return (
    <main className="min-h-screen overflow-hidden bg-[radial-gradient(circle_at_top_left,#1646a9,transparent_35%),linear-gradient(135deg,#041025,#07162f_55%,#04251f)] px-4 py-6 text-white sm:px-8">
      <div className="pointer-events-none fixed inset-0 opacity-40 [background-image:radial-gradient(circle,rgba(255,255,255,.22)_1px,transparent_1px)] [background-size:32px_32px]" />
      <nav className="glass relative z-10 mx-auto flex max-w-7xl items-center justify-between rounded-full px-5 py-4">
        <div>
          <p className="text-xs uppercase tracking-[.35em] text-emerald">{brandName}</p>
          <h1 className="text-lg font-black sm:text-2xl">{productName}</h1>
        </div>
        <button className="rounded-full bg-emerald px-5 py-3 text-sm font-bold text-navy">Launch Portal</button>
      </nav>

      <section className="relative z-10 mx-auto grid max-w-7xl gap-10 py-16 lg:grid-cols-[1.05fr_.95fr] lg:items-center">
        <div>
          <div className="mb-5 inline-flex items-center gap-2 rounded-full border border-emerald/40 bg-emerald/10 px-4 py-2 text-sm text-emerald"><Sparkles size={16}/> Enterprise SaaS • Vault • CRM • Franchise • White Label</div>
          <h2 className="max-w-4xl text-5xl font-black leading-tight sm:text-7xl">Premium secure cloud document vault for families, customers and franchises.</h2>
          <p className="mt-6 max-w-2xl text-lg text-white/72">A production-ready Next.js and Supabase blueprint with RBAC, RLS, signed storage access, wallet payments, OCR workflows, consent, QR verification, analytics and support operations.</p>
          <div className="mt-8 flex flex-wrap gap-3">
            {roles.map((role) => <span key={role} className="rounded-full border border-white/15 bg-white/10 px-4 py-2 text-xs font-bold">{role.replaceAll('_', ' ')}</span>)}
          </div>
        </div>
        <div className="glass animate-float rounded-[2.5rem] p-4">
          <SecureDocumentPreview customerName="Lakshmi Chowdary" />
        </div>
      </section>

      <section className="relative z-10 mx-auto grid max-w-7xl gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {metrics.map(([label, value]) => <article key={label} className="glass rounded-3xl p-5"><p className="text-sm text-white/60">{label}</p><strong className="mt-2 block text-3xl">{value}</strong></article>)}
      </section>

      <section className="relative z-10 mx-auto mt-10 grid max-w-7xl gap-5 md:grid-cols-2 xl:grid-cols-4">
        {modules.map(({ title, text, icon: Icon }) => <article key={title} className="glass rounded-[2rem] p-6"><Icon className="mb-5 text-emerald"/><h3 className="text-xl font-black">{title}</h3><p className="mt-3 text-sm leading-6 text-white/68">{text}</p></article>)}
      </section>

      <section className="relative z-10 mx-auto my-10 max-w-7xl rounded-[2rem] border border-white/10 bg-white/5 p-6">
        <div className="mb-4 flex items-center gap-3"><LockKeyhole className="text-emerald"/><h3 className="text-2xl font-black">Unlimited Document Categories</h3></div>
        <div className="flex flex-wrap gap-2">{documentCategories.map((category) => <span key={category} className="rounded-full bg-white/10 px-3 py-2 text-xs text-white/75">{category}</span>)}</div>
      </section>

      <section className="relative z-10 mx-auto mb-16 grid max-w-7xl gap-5 md:grid-cols-3">
        <div className="glass rounded-[2rem] p-6"><Shield className="text-emerald"/><h3 className="mt-4 text-xl font-black">No raw storage URLs</h3><p className="mt-2 text-white/65">Documents are encrypted, stored privately and served only through temporary authorization workflows.</p></div>
        <div className="glass rounded-[2rem] p-6"><DownloadCloud className="text-emerald"/><h3 className="mt-4 text-xl font-black">Pay before download</h3><p className="mt-2 text-white/65">Original files become available only after approval, policy checks and successful payment or wallet debit.</p></div>
        <div className="glass rounded-[2rem] p-6"><LockKeyhole className="text-emerald"/><h3 className="mt-4 text-xl font-black">Preview-only protection</h3><p className="mt-2 text-white/65">PDF toolbar, print, save, drag and context menu actions are blocked while watermark overlays remain visible.</p></div>
      </section>
    </main>
  );
}

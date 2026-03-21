import LoginForm from '@/components/login-form'

export default function LoginPage() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-bg px-6">
      <div className="w-full max-w-[380px]">
        <p className="font-mono text-[10px] tracking-[0.15em] uppercase text-muted mb-2">
          Ninth Circuit Research
        </p>
        <h1 className="text-[28px] font-normal tracking-tight mb-3 leading-tight text-text">
          Asylum Cases Database
        </h1>
        <p className="text-sm text-muted mb-8 pb-8 border-b border-border leading-relaxed">
          Search and filter extracted legal features from Ninth Circuit asylum court decisions.
        </p>
        <LoginForm />
        <p className="mt-8 text-center font-mono text-[10px] tracking-wider uppercase text-muted">
          Authorized users only
        </p>
      </div>
    </div>
  )
}

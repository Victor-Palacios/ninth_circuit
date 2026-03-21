import LoginForm from '@/components/login-form'

export default function LoginPage() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-bg px-6">
      <div className="w-full max-w-[440px]">
        <p className="font-mono text-xs tracking-[0.15em] uppercase text-muted mb-3">
          Ninth Circuit Research
        </p>
        <h1 className="text-4xl font-normal tracking-tight mb-4 leading-tight text-text">
          Asylum Cases Database
        </h1>
        <p className="text-base text-muted mb-10 pb-10 border-b border-border leading-relaxed">
          Search and filter extracted legal features from Ninth Circuit asylum court decisions.
        </p>
        <LoginForm />
        <p className="mt-10 text-center font-mono text-xs tracking-wider uppercase text-muted">
          Authorized users only
        </p>
      </div>
    </div>
  )
}

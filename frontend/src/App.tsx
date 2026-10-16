import { ApiStatus } from './components/ApiStatus'

function App() {
  return (
    <main className="flex min-h-screen items-center justify-center bg-slate-50 px-4">
      <div className="max-w-xl text-center">
        <h1 className="text-4xl font-bold tracking-tight text-slate-900">Tender Insight Hub</h1>
        <p className="mt-4 text-lg text-slate-600">
          Discover, understand and assess South African public tenders.
        </p>
        <div className="mt-8">
          <ApiStatus />
        </div>
      </div>
    </main>
  )
}

export default App

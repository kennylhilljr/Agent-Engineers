export default function Home() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center p-24 bg-gray-900 text-white">
      <div className="z-10 max-w-5xl w-full items-center justify-between font-mono text-sm">
        <h1 className="text-4xl font-bold mb-4">AI Coding Dashboard</h1>
        <p className="text-xl mb-8">Next.js 14 + TypeScript + Tailwind CSS + CopilotKit</p>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="p-6 border border-gray-700 rounded-lg bg-gray-800">
            <h2 className="text-2xl font-semibold mb-2">Next.js 14</h2>
            <p className="text-gray-400">App Router enabled with TypeScript</p>
          </div>
          <div className="p-6 border border-gray-700 rounded-lg bg-gray-800">
            <h2 className="text-2xl font-semibold mb-2">Tailwind CSS</h2>
            <p className="text-gray-400">Dark theme configured as default</p>
          </div>
          <div className="p-6 border border-gray-700 rounded-lg bg-gray-800">
            <h2 className="text-2xl font-semibold mb-2">CopilotKit</h2>
            <p className="text-gray-400">AI integration ready</p>
          </div>
          <div className="p-6 border border-gray-700 rounded-lg bg-gray-800">
            <h2 className="text-2xl font-semibold mb-2">TypeScript</h2>
            <p className="text-gray-400">Strict mode enabled</p>
          </div>
        </div>
      </div>
    </main>
  );
}

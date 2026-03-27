'use client'

import { useEffect } from 'react'
import Link from 'next/link'

export default function RootError({
  error,
  reset,
}: {
  error: Error & { digest?: string }
  reset: () => void
}) {
  useEffect(() => {
    console.error('[Root Error]', error.message)
  }, [error])

  return (
    <div className="min-h-screen bg-black text-white flex items-center justify-center p-4">
      <div className="max-w-md w-full rounded-xl border border-red-500/30 bg-red-500/10 p-8 text-center">
        <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-red-500/20 text-2xl">
          !
        </div>
        <h2 className="text-xl font-bold text-red-300 mb-2">
          Something went wrong
        </h2>
        <p className="text-sm text-gray-400 mb-6">
          {error.message || 'An unexpected error occurred. Please try again.'}
        </p>
        {error.digest && (
          <p className="text-xs text-gray-500 mb-4 font-mono">
            Error ID: {error.digest}
          </p>
        )}
        <div className="flex items-center justify-center gap-3">
          <button
            onClick={reset}
            className="rounded-lg px-4 py-2 text-sm font-medium bg-orange-600 hover:bg-orange-500 text-white transition-colors"
          >
            Try again
          </button>
          <Link
            href="/"
            className="rounded-lg px-4 py-2 text-sm font-medium bg-gray-800 hover:bg-gray-700 border border-gray-700 text-white transition-colors"
          >
            Go Home
          </Link>
        </div>
      </div>
    </div>
  )
}

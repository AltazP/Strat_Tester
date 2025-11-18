"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

export default function HomePage() {
  const router = useRouter();

  useEffect(() => {
    router.replace("/backtesting");
  }, [router]);

  return (
    <div className="flex items-center justify-center min-h-[400px]">
      <div className="text-center">
        <div className="inline-block animate-spin rounded-full h-12 w-12 border-4 border-solid border-primary border-r-transparent"></div>
        <p className="mt-4 text-gray-500 dark:text-gray-400">Redirecting to Backtesting...</p>
      </div>
    </div>
  );
}

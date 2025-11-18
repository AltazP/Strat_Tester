"use client";

export default function SupportPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-gray-800 dark:text-white/90 mb-2">
          Support & About
        </h1>
        <p className="text-sm text-gray-500 dark:text-gray-400">
          Information about the application and how to get help
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* About Section */}
        <div className="p-6 rounded-xl border border-stroke dark:border-strokedark bg-white dark:bg-gray-900">
          <h2 className="text-xl font-semibold text-gray-800 dark:text-white/90 mb-4">
            About Strategy Tester
          </h2>
          <div className="space-y-4 text-gray-600 dark:text-gray-400">
            <p>
              Strategy Tester is a comprehensive trading platform that allows you to backtest, 
              paper trade, and manage trading strategies with OANDA accounts.
            </p>
            <div>
              <h3 className="font-semibold text-gray-800 dark:text-white/90 mb-2">Features:</h3>
              <ul className="list-disc list-inside space-y-1 ml-2">
                <li>Backtesting with historical data</li>
                <li>Paper trading with OANDA demo accounts</li>
                <li>Real-time position and session management</li>
                <li>Multiple trading strategies</li>
                <li>Account and position monitoring</li>
              </ul>
            </div>
          </div>
        </div>

        {/* Support Section */}
        <div className="p-6 rounded-xl border border-stroke dark:border-strokedark bg-white dark:bg-gray-900">
          <h2 className="text-xl font-semibold text-gray-800 dark:text-white/90 mb-4">
            Getting Help
          </h2>
          <div className="space-y-4 text-gray-600 dark:text-gray-400">
            <p>
              If you need assistance or have questions about using Strategy Tester, 
              please refer to the following resources:
            </p>
            <div>
              <h3 className="font-semibold text-gray-800 dark:text-white/90 mb-2">Documentation:</h3>
              <ul className="space-y-2">
                <li>
                  • View the{" "}
                  <a
                    href="https://github.com/AltazP/Strat_Tester/"
                    className="text-brand-600 underline hover:text-brand-800"
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    GitHub Tutorial &amp; README
                  </a>
                  {" "}for documentation and detailed instructions
                </li>
                <li>• Consult OANDA API documentation for account setup</li>
              </ul>
            </div>
            <div>
              <h3 className="font-semibold text-gray-800 dark:text-white/90 mb-2">Common Issues:</h3>
              <ul className="space-y-2">
                <li>• Ensure your OANDA API keys are correctly configured</li>
                <li>• Verify your account has sufficient margin for trading</li>
                <li>• Check that sessions are properly started before trading</li>
              </ul>
            </div>
          </div>
        </div>

        {/* Personal Information */}
        <div className="p-6 rounded-xl border border-stroke dark:border-strokedark bg-white dark:bg-gray-900">
          <h2 className="text-xl font-semibold text-gray-800 dark:text-white/90 mb-4">
            Developer Information
          </h2>
          <div className="space-y-2 text-gray-600 dark:text-gray-400">
            <p>
              <strong className="text-gray-800 dark:text-white/90">Name:</strong> Altaz Punja
            </p>
            <p>
              <strong className="text-gray-800 dark:text-white/90">School:</strong> University of Waterloo
            </p>
            <p>
              <strong className="text-gray-800 dark:text-white/90">Program:</strong> Bachelor of Computer Science
            </p>
            <p>
              <strong className="text-gray-800 dark:text-white/90">Email:</strong>{" "}
              <a
                href="altazp@gmail.com"
                className="text-brand-600 underline hover:text-brand-800"
              >
                altazp@gmail.com
              </a>
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
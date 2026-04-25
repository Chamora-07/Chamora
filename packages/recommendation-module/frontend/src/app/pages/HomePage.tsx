import { Activity, ArrowRight, CheckCircle2, Shield, Zap, BarChart3 } from 'lucide-react';
import { Link } from 'react-router';

export function HomePage() {
  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 via-indigo-50 to-purple-50">
      {/* Navigation */}
      <nav className="bg-white/90 backdrop-blur-md border-b border-slate-200 px-6 py-4 shadow-sm">
        <div className="max-w-7xl mx-auto flex justify-between items-center">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-gradient-to-br from-indigo-500 to-purple-600 rounded-lg flex items-center justify-center">
              <Activity className="w-6 h-6 text-white" />
            </div>
            <h1 className="text-xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-indigo-600 to-purple-600">
              Chamora
            </h1>
          </div>
          <div className="flex items-center gap-4">
            <Link
              to="/login"
              className="px-6 py-2.5 text-slate-700 hover:text-indigo-600 font-medium transition-colors"
            >
              Login
            </Link>
            <Link
              to="/login"
              className="px-6 py-2.5 bg-gradient-to-br from-indigo-500 to-purple-600 text-white rounded-lg hover:from-indigo-600 hover:to-purple-700 transition-all shadow-md hover:shadow-lg font-medium"
            >
              Get Started
            </Link>
          </div>
        </div>
      </nav>

      {/* Hero Section */}
      <div className="max-w-7xl mx-auto px-6 py-20">
        <div className="text-center mb-16">
          <h1 className="text-6xl font-bold text-slate-800 mb-6">
            AI-Powered Performance
            <span className="block text-transparent bg-clip-text bg-gradient-to-r from-indigo-600 to-purple-600">
              Intelligence Engine
            </span>
          </h1>
          <p className="text-xl text-slate-600 mb-8 max-w-3xl mx-auto">
            Streamline your application testing and performance analysis with intelligent insights, 
            automated anomaly detection, and comprehensive test cycle management.
          </p>
          <Link
            to="/login"
            className="inline-flex items-center gap-3 px-8 py-4 bg-gradient-to-br from-indigo-500 to-purple-600 text-white rounded-xl hover:from-indigo-600 hover:to-purple-700 transition-all shadow-lg hover:shadow-xl text-lg font-semibold"
          >
            Start Your Free Trial
            <ArrowRight className="w-5 h-5" />
          </Link>
        </div>

        {/* Features Grid */}
        <div className="grid grid-cols-3 gap-8 mt-20">
          {/* Feature 1 */}
          <div className="bg-white/80 backdrop-blur-sm border border-slate-200 rounded-xl p-8 hover:border-indigo-300 hover:shadow-lg transition-all">
            <div className="w-14 h-14 bg-gradient-to-br from-indigo-500 to-purple-600 rounded-lg flex items-center justify-center mb-6">
              <Zap className="w-7 h-7 text-white" />
            </div>
            <h3 className="text-xl font-bold text-slate-800 mb-3">Intelligent Automation</h3>
            <p className="text-slate-600">
              Automate your testing workflows with AI-powered insights and recommendations for optimal performance.
            </p>
          </div>

          {/* Feature 2 */}
          <div className="bg-white/80 backdrop-blur-sm border border-slate-200 rounded-xl p-8 hover:border-indigo-300 hover:shadow-lg transition-all">
            <div className="w-14 h-14 bg-gradient-to-br from-purple-500 to-pink-600 rounded-lg flex items-center justify-center mb-6">
              <BarChart3 className="w-7 h-7 text-white" />
            </div>
            <h3 className="text-xl font-bold text-slate-800 mb-3">Performance Analytics</h3>
            <p className="text-slate-600">
              Deep insights into application performance with real-time monitoring and comprehensive reporting.
            </p>
          </div>

          {/* Feature 3 */}
          <div className="bg-white/80 backdrop-blur-sm border border-slate-200 rounded-xl p-8 hover:border-indigo-300 hover:shadow-lg transition-all">
            <div className="w-14 h-14 bg-gradient-to-br from-emerald-500 to-teal-600 rounded-lg flex items-center justify-center mb-6">
              <Shield className="w-7 h-7 text-white" />
            </div>
            <h3 className="text-xl font-bold text-slate-800 mb-3">Anomaly Detection</h3>
            <p className="text-slate-600">
              Automatically detect and alert on performance anomalies before they impact your users.
            </p>
          </div>
        </div>

        {/* CTA Section */}
        <div className="mt-20 bg-gradient-to-br from-indigo-500 to-purple-600 rounded-2xl p-12 text-center text-white shadow-2xl">
          <h2 className="text-3xl font-bold mb-4">Ready to Transform Your Testing?</h2>
          <p className="text-lg text-indigo-100 mb-8 max-w-2xl mx-auto">
            Join thousands of developers and QA engineers who trust Chamora for their performance testing needs.
          </p>
          <Link
            to="/login"
            className="inline-flex items-center gap-3 px-8 py-4 bg-white text-indigo-600 rounded-xl hover:bg-indigo-50 transition-all shadow-lg hover:shadow-xl text-lg font-semibold"
          >
            Get Started Now
            <CheckCircle2 className="w-5 h-5" />
          </Link>
        </div>
      </div>
    </div>
  );
}

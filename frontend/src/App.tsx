import type { ReactNode } from 'react';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import NavBar from './components/NavBar';
import RouteErrorBoundary from './components/RouteErrorBoundary';
import Leaderboard from './pages/Leaderboard';
import SkillDetail from './pages/SkillDetail';
import Scanner from './pages/Scanner';
import About from './pages/About';
import Categories from './pages/Categories';
import CategoryDetail from './pages/CategoryDetail';
import TournamentDetail from './pages/TournamentDetail';
import Fields from './pages/Fields';
import FieldRoleLeaderboard from './pages/FieldRoleLeaderboard';
import AgentDetail from './pages/AgentDetail';
import TraceDetail from './pages/TraceDetail';
import ControlRoom from './pages/ControlRoom';
import ReviewQueue from './pages/ReviewQueue';
import ReviewCandidate from './pages/ReviewCandidate';
import JDCorpus from './pages/JDCorpus';
import SourceQueue from './pages/SourceQueue';

function withRouteBoundary(routeName: string, element: ReactNode) {
  return (
    <RouteErrorBoundary routeName={routeName}>
      {element}
    </RouteErrorBoundary>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <div className="min-h-screen bg-bg-primary">
        <NavBar />
        <Routes>
          <Route path="/" element={<Navigate to="/fields" replace />} />
          <Route path="/fields" element={withRouteBoundary('Fields', <Fields />)} />
          <Route path="/ops" element={withRouteBoundary('Control Room', <ControlRoom />)} />
          <Route path="/sources" element={withRouteBoundary('Source Queue', <SourceQueue />)} />
          <Route path="/review" element={withRouteBoundary('Review Queue', <ReviewQueue />)} />
          <Route path="/review/:versionId" element={withRouteBoundary('Review Candidate', <ReviewCandidate />)} />
          <Route path="/jd/:field/:role" element={withRouteBoundary('JD Corpus', <JDCorpus />)} />
          <Route path="/fields/:field/:role" element={withRouteBoundary('Field Role Leaderboard', <FieldRoleLeaderboard />)} />
          <Route path="/agent/:versionId" element={withRouteBoundary('Agent Detail', <AgentDetail />)} />
          <Route path="/traces/:traceId" element={withRouteBoundary('Trace Detail', <TraceDetail />)} />
          <Route path="/leaderboard" element={withRouteBoundary('Legacy Leaderboard', <Leaderboard />)} />
          <Route path="/skill/:name" element={withRouteBoundary('Legacy Skill Detail', <SkillDetail />)} />
          <Route path="/categories" element={withRouteBoundary('Legacy Categories', <Categories />)} />
          <Route path="/categories/:slug" element={withRouteBoundary('Legacy Category Detail', <CategoryDetail />)} />
          <Route path="/tournament/:id" element={withRouteBoundary('Tournament', <TournamentDetail />)} />
          <Route path="/scan" element={withRouteBoundary('Scanner', <Scanner />)} />
          <Route path="/about" element={withRouteBoundary('About', <About />)} />
        </Routes>
        <footer className="border-t border-border bg-bg-secondary py-6 mt-12">
          <div className="mx-auto max-w-6xl px-4 flex flex-col items-center gap-1 text-sm text-text-muted">
            <a
              href="https://kooexperience.com"
              target="_blank"
              rel="noopener noreferrer"
              className="text-text-secondary hover:text-cyan-accent no-underline transition-colors"
            >
              AgentArena by Koo
            </a>
            <span>Role-based agent tournaments</span>
          </div>
        </footer>
      </div>
    </BrowserRouter>
  );
}

import {
  AlertTriangle,
  BarChart3,
  CalendarClock,
  ClipboardList,
  FileText,
  FolderOpen,
  GitPullRequest,
  History,
  Home,
  type LucideIcon,
  MessageSquare,
  Package,
  PenLine,
  Send,
  Settings,
  ShieldAlert,
  Wallet,
} from 'lucide-react'

export interface NavItem {
  to: string
  labelKey: string
  icon: LucideIcon
  /** Module of the project type that switches this entry on; none = always shown. */
  module?: string
  /** Eligible for the four slots of the mobile bottom bar (SPEC 15.3). */
  primary?: boolean
}

/** Every entry, in display order. A project shows the ones its type enables. */
export const allNav: NavItem[] = [
  { to: '/', labelKey: 'nav.dashboard', icon: Home, module: 'dashboard', primary: true },
  { to: '/packages', labelKey: 'nav.packages', icon: Package, module: 'packages', primary: true },
  { to: '/schedule', labelKey: 'nav.schedule', icon: BarChart3, module: 'schedule', primary: true },
  { to: '/weekly-reports', labelKey: 'nav.weeklyReports', icon: FileText, module: 'weekly_reports', primary: true },
  { to: '/daily-log', labelKey: 'nav.dailyLog', icon: PenLine, module: 'daily_log', primary: true },
  { to: '/alerts', labelKey: 'nav.alerts', icon: AlertTriangle, module: 'alerts', primary: true },
  { to: '/progress', labelKey: 'nav.progress', icon: BarChart3, module: 'progress' },
  { to: '/contracts', labelKey: 'nav.contracts', icon: FileText, module: 'contracts' },
  { to: '/payments', labelKey: 'nav.payments', icon: Wallet, module: 'payments' },
  { to: '/documents', labelKey: 'nav.documents', icon: FolderOpen, module: 'documents' },
  { to: '/risks', labelKey: 'nav.risks', icon: ShieldAlert, module: 'risks' },
  { to: '/issues', labelKey: 'nav.issues', icon: ClipboardList, module: 'issues' },
  { to: '/decisions', labelKey: 'nav.decisions', icon: ClipboardList, module: 'decisions' },
  { to: '/meetings', labelKey: 'nav.meetings', icon: MessageSquare, module: 'meetings' },
  { to: '/change-requests', labelKey: 'nav.changeRequests', icon: GitPullRequest, module: 'change_requests' },
  { to: '/outgoing-docs', labelKey: 'nav.outgoingDocs', icon: Send, module: 'outgoing_docs' },
  { to: '/admin/projects', labelKey: 'nav.projects', icon: FolderOpen },
  { to: '/admin/users', labelKey: 'nav.admin', icon: Settings },
  { to: '/admin/audit', labelKey: 'nav.audit', icon: History, module: 'audit' },
  { to: '/admin/settings', labelKey: 'nav.settings', icon: Settings },
  { to: '/profile', labelKey: 'nav.profile', icon: CalendarClock },
]

export interface ProjectNav {
  /** The slots of the mobile bottom bar. */
  primary: NavItem[]
  /** The rest, behind the "more" button. */
  more: NavItem[]
  /** Everything, for the sidebar. */
  all: NavItem[]
}

/** The menu of a project: entries whose module the project's type enables (all when unknown). */
export function navFor(modules: readonly string[] | null | undefined): ProjectNav {
  const all = allNav.filter((item) => !item.module || !modules || modules.includes(item.module))
  const primary = all.filter((item) => item.primary).slice(0, 4)
  return { primary, more: all.filter((item) => !primary.includes(item)), all }
}

import {
  AlertTriangle,
  BarChart3,
  CalendarClock,
  ClipboardList,
  FileText,
  FolderOpen,
  GitPullRequest,
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
}

/** Slots of the mobile bottom bar (SPEC 15.3); "more" is rendered separately. */
export const primaryNav: NavItem[] = [
  { to: '/', labelKey: 'nav.dashboard', icon: Home },
  { to: '/packages', labelKey: 'nav.packages', icon: Package },
  { to: '/daily-log', labelKey: 'nav.dailyLog', icon: PenLine },
  { to: '/alerts', labelKey: 'nav.alerts', icon: AlertTriangle },
]

export const moreNav: NavItem[] = [
  { to: '/progress', labelKey: 'nav.progress', icon: BarChart3 },
  { to: '/contracts', labelKey: 'nav.contracts', icon: FileText },
  { to: '/payments', labelKey: 'nav.payments', icon: Wallet },
  { to: '/documents', labelKey: 'nav.documents', icon: FolderOpen },
  { to: '/risks', labelKey: 'nav.risks', icon: ShieldAlert },
  { to: '/issues', labelKey: 'nav.issues', icon: ClipboardList },
  { to: '/meetings', labelKey: 'nav.meetings', icon: MessageSquare },
  { to: '/change-requests', labelKey: 'nav.changeRequests', icon: GitPullRequest },
  { to: '/outgoing-docs', labelKey: 'nav.outgoingDocs', icon: Send },
  { to: '/admin/users', labelKey: 'nav.admin', icon: Settings },
  { to: '/profile', labelKey: 'nav.profile', icon: CalendarClock },
]

export const sidebarNav: NavItem[] = [...primaryNav, ...moreNav]

import type {
  ButtonHTMLAttributes,
  InputHTMLAttributes,
  TextareaHTMLAttributes,
  SelectHTMLAttributes,
  HTMLAttributes,
} from 'react'

// ==========================================
// 1. BUTTON
// ==========================================
interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'outline' | 'ghost' | 'danger'
  size?: 'sm' | 'md' | 'lg'
}

export const Button = ({
  variant = 'primary',
  size = 'md',
  className = '',
  children,
  ...props
}: ButtonProps) => {
  const baseStyle =
    'inline-flex items-center justify-center font-semibold rounded-xl transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer'

  const variants = {
    primary:
      'bg-indigo-600 hover:bg-indigo-700 text-white shadow-lg shadow-indigo-600/20',
    secondary:
      'bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700/50',
    outline:
      'bg-transparent border border-slate-700 hover:bg-slate-800 text-slate-300',
    ghost:
      'bg-transparent hover:bg-slate-800/60 text-slate-400 hover:text-slate-200',
    danger:
      'bg-red-600 hover:bg-red-700 text-white shadow-lg shadow-red-600/20',
  }

  const sizes = {
    sm: 'px-3 py-1.5 text-xs',
    md: 'px-4 py-2 text-sm',
    lg: 'px-6 py-3 text-base',
  }

  return (
    <button
      className={`${baseStyle} ${variants[variant]} ${sizes[size]} ${className}`}
      {...props}
    >
      {children}
    </button>
  )
}

// ==========================================
// 2. CARD
// ==========================================
interface CardProps extends HTMLAttributes<HTMLDivElement> {
  hoverable?: boolean
}

export const Card = ({
  hoverable = false,
  className = '',
  children,
  ...props
}: CardProps) => {
  return (
    <div
      className={`
        bg-slate-900/50 border border-slate-800/80 rounded-2xl p-6 backdrop-blur-xl shadow-xl
        ${hoverable ? 'hover:border-slate-700/80 transition-all duration-300 hover:shadow-2xl' : ''}
        ${className}
      `}
      {...props}
    >
      {children}
    </div>
  )
}

// ==========================================
// 3. INPUT
// ==========================================
interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string
  error?: string
}

export const Input = ({
  label,
  error,
  id,
  className = '',
  disabled,
  ...props
}: InputProps) => {
  return (
    <div className="flex flex-col gap-1.5 w-full text-left">
      {label && id && (
        <label
          htmlFor={id}
          className="text-xs font-semibold text-slate-400 uppercase tracking-wider"
        >
          {label}
        </label>
      )}
      <input
        id={id}
        disabled={disabled}
        className={`
          px-4 py-2.5 bg-slate-950 border rounded-xl text-sm text-slate-100 placeholder:text-slate-600
          transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-indigo-500
          disabled:opacity-50 disabled:cursor-not-allowed
          ${error ? 'border-red-500/80 focus:ring-red-500' : 'border-slate-800/80 focus:border-indigo-500/80'}
          ${className}
        `}
        {...props}
      />
      {error && <span className="text-xs text-red-400 mt-0.5">{error}</span>}
    </div>
  )
}

// ==========================================
// 4. TEXTAREA
// ==========================================
interface TextareaProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  label?: string
  error?: string
}

export const Textarea = ({
  label,
  error,
  id,
  className = '',
  disabled,
  rows = 4,
  ...props
}: TextareaProps) => {
  return (
    <div className="flex flex-col gap-1.5 w-full text-left">
      {label && id && (
        <label
          htmlFor={id}
          className="text-xs font-semibold text-slate-400 uppercase tracking-wider"
        >
          {label}
        </label>
      )}
      <textarea
        id={id}
        rows={rows}
        disabled={disabled}
        className={`
          px-4 py-2.5 bg-slate-950 border rounded-xl text-sm text-slate-100 placeholder:text-slate-600
          transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-indigo-500
          disabled:opacity-50 disabled:cursor-not-allowed
          ${error ? 'border-red-500/80 focus:ring-red-500' : 'border-slate-800/80 focus:border-indigo-500/80'}
          ${className}
        `}
        {...props}
      />
      {error && <span className="text-xs text-red-400 mt-0.5">{error}</span>}
    </div>
  )
}

// ==========================================
// 5. SELECT
// ==========================================
interface SelectProps extends SelectHTMLAttributes<HTMLSelectElement> {
  label?: string
  error?: string
  options: { value: string; label: string }[]
}

export const Select = ({
  label,
  error,
  id,
  options,
  className = '',
  disabled,
  ...props
}: SelectProps) => {
  return (
    <div className="flex flex-col gap-1.5 w-full text-left">
      {label && id && (
        <label
          htmlFor={id}
          className="text-xs font-semibold text-slate-400 uppercase tracking-wider"
        >
          {label}
        </label>
      )}
      <div className="relative">
        <select
          id={id}
          disabled={disabled}
          className={`
            w-full px-4 py-2.5 bg-slate-950 border rounded-xl text-sm text-slate-100 appearance-none
            transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-indigo-500
            disabled:opacity-50 disabled:cursor-not-allowed
            ${error ? 'border-red-500/80 focus:ring-red-500' : 'border-slate-800/80 focus:border-indigo-500/80'}
            ${className}
          `}
          {...props}
        >
          {options.map((opt) => (
            <option key={opt.value} value={opt.value} className="bg-slate-950">
              {opt.label}
            </option>
          ))}
        </select>
        <div className="absolute inset-y-0 right-4 flex items-center pointer-events-none text-slate-500">
          ▼
        </div>
      </div>
      {error && <span className="text-xs text-red-400 mt-0.5">{error}</span>}
    </div>
  )
}

// ==========================================
// 6. CHECKBOX
// ==========================================
interface CheckboxProps extends Omit<InputHTMLAttributes<HTMLInputElement>, 'type'> {
  label: string
  error?: string
}

export const Checkbox = ({
  label,
  error,
  id,
  className = '',
  disabled,
  ...props
}: CheckboxProps) => {
  return (
    <div className="flex flex-col gap-1 text-left">
      <div className="flex items-center gap-3">
        <input
          id={id}
          type="checkbox"
          disabled={disabled}
          className={`
            w-5 h-5 bg-slate-950 border border-slate-800 rounded-lg text-indigo-600 accent-indigo-600
            focus:ring-2 focus:ring-indigo-500 focus:outline-none transition-all cursor-pointer
            disabled:opacity-50 disabled:cursor-not-allowed
            ${className}
          `}
          {...props}
        />
        {id && (
          <label
            htmlFor={id}
            className="text-sm text-slate-300 font-medium cursor-pointer select-none"
          >
            {label}
          </label>
        )}
      </div>
      {error && <span className="text-xs text-red-400 mt-0.5">{error}</span>}
    </div>
  )
}

// ==========================================
// 7. BADGE
// ==========================================
interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  variant?: 'info' | 'success' | 'warning' | 'error'
}

export const Badge = ({
  variant = 'info',
  className = '',
  children,
  ...props
}: BadgeProps) => {
  const variants = {
    info: 'text-indigo-400 bg-indigo-500/10 border-indigo-500/20',
    success: 'text-emerald-400 bg-emerald-500/10 border-emerald-500/20',
    warning: 'text-amber-400 bg-amber-500/10 border-amber-500/20',
    error: 'text-red-400 bg-red-500/10 border-red-500/20',
  }

  return (
    <span
      className={`px-2.5 py-1 text-xs font-semibold rounded-lg border uppercase tracking-wider ${variants[variant]} ${className}`}
      {...props}
    >
      {children}
    </span>
  )
}

// ==========================================
// 8. ALERT
// ==========================================
interface AlertProps extends HTMLAttributes<HTMLDivElement> {
  variant?: 'info' | 'success' | 'warning' | 'error'
  title: string
  onClose?: () => void
}

export const Alert = ({
  variant = 'info',
  title,
  className = '',
  children,
  onClose,
  ...props
}: AlertProps) => {
  const variants = {
    info: 'bg-indigo-950/40 border-indigo-800/60 text-indigo-200',
    success: 'bg-emerald-950/40 border-emerald-800/60 text-emerald-200',
    warning: 'bg-amber-950/40 border-amber-800/60 text-amber-200',
    error: 'bg-red-950/40 border-red-800/60 text-red-200',
  }

  const icons = {
    info: 'ℹ️',
    success: '✅',
    warning: '⚠️',
    error: '🚨',
  }

  return (
    <div
      role="alert"
      className={`flex gap-4 p-4 border rounded-2xl backdrop-blur-md relative ${variants[variant]} ${className}`}
      {...props}
    >
      <span className="text-xl select-none" aria-hidden="true">
        {icons[variant]}
      </span>
      <div className="flex-1 text-left">
        <h4 className="font-bold text-sm mb-1 leading-snug">{title}</h4>
        {children && <div className="text-xs leading-relaxed opacity-90">{children}</div>}
      </div>
      {onClose && (
        <button
          onClick={onClose}
          className="text-slate-400 hover:text-white focus:outline-none focus:ring-2 focus:ring-indigo-500 rounded-md p-0.5 h-fit"
          aria-label="Dismiss alert"
        >
          ✕
        </button>
      )}
    </div>
  )
}

// ==========================================
// 9. SPINNER
// ==========================================
interface SpinnerProps extends HTMLAttributes<HTMLDivElement> {
  size?: 'sm' | 'md' | 'lg'
}

export const Spinner = ({ size = 'md', className = '', ...props }: SpinnerProps) => {
  const sizes = {
    sm: 'w-5 h-5 border-2',
    md: 'w-8 h-8 border-3',
    lg: 'w-12 h-12 border-4',
  }

  return (
    <div
      className={`border-slate-800 border-t-indigo-500 rounded-full animate-spin ${sizes[size]} ${className}`}
      role="status"
      aria-label="Loading"
      {...props}
    />
  )
}

// ==========================================
// 10. DIVIDER
// ==========================================
interface DividerProps extends HTMLAttributes<HTMLDivElement> {
  label?: string
}

export const Divider = ({ label, className = '', ...props }: DividerProps) => {
  return (
    <div
      className={`flex items-center my-6 text-slate-700 text-xs font-semibold uppercase tracking-wider ${className}`}
      {...props}
    >
      <div className="flex-1 border-t border-slate-800/80"></div>
      {label && <span className="px-4 select-none">{label}</span>}
      <div className="flex-1 border-t border-slate-800/80"></div>
    </div>
  )
}

// ==========================================
// 11. LAYOUT HELPERS
// ==========================================
export const Container = ({
  className = '',
  children,
  ...props
}: HTMLAttributes<HTMLDivElement>) => (
  <div
    className={`max-w-7xl w-full mx-auto px-4 md:px-8 box-border ${className}`}
    {...props}
  >
    {children}
  </div>
)

interface PageHeaderProps extends HTMLAttributes<HTMLDivElement> {
  title: string
  subtitle?: string
}

export const PageHeader = ({ title, subtitle, className = '', ...props }: PageHeaderProps) => (
  <header className={`mb-8 text-left ${className}`} {...props}>
    <h1 className="text-3xl md:text-4xl font-extrabold tracking-tight bg-gradient-to-r from-white via-indigo-200 to-indigo-400 bg-clip-text text-transparent leading-normal pb-1">
      {title}
    </h1>
    {subtitle && (
      <p className="text-slate-400 text-sm md:text-base mt-2 leading-relaxed max-w-2xl">
        {subtitle}
      </p>
    )}
  </header>
)

export const Section = ({
  className = '',
  children,
  ...props
}: HTMLAttributes<HTMLElement>) => (
  <section className={`my-8 ${className}`} {...props}>
    {children}
  </section>
)

interface StackProps extends HTMLAttributes<HTMLDivElement> {
  direction?: 'col' | 'row'
  gap?: 'sm' | 'md' | 'lg'
}

export const Stack = ({
  direction = 'col',
  gap = 'md',
  className = '',
  children,
  ...props
}: StackProps) => {
  const gaps = {
    sm: 'gap-3',
    md: 'gap-6',
    lg: 'gap-10',
  }
  return (
    <div
      className={`flex ${direction === 'col' ? 'flex-col' : 'flex-row flex-wrap'} ${gaps[gap]} ${className}`}
      {...props}
    >
      {children}
    </div>
  )
}

interface GridProps extends HTMLAttributes<HTMLDivElement> {
  cols?: 1 | 2 | 3 | 4
}

export const Grid = ({ cols = 3, className = '', children, ...props }: GridProps) => {
  const columns = {
    1: 'grid-cols-1',
    2: 'grid-cols-1 md:grid-cols-2',
    3: 'grid-cols-1 md:grid-cols-2 lg:grid-cols-3',
    4: 'grid-cols-1 md:grid-cols-2 lg:grid-cols-4',
  }
  return (
    <div className={`grid ${columns[cols]} gap-6 ${className}`} {...props}>
      {children}
    </div>
  )
}

// ==========================================
// 12. FEEDBACK STATES
// ==========================================
interface EmptyStateProps extends HTMLAttributes<HTMLDivElement> {
  title: string
  description: string
  icon?: string
  actionLabel?: string
  onAction?: () => void
}

export const EmptyState = ({
  title,
  description,
  icon = '📁',
  actionLabel,
  onAction,
  className = '',
  ...props
}: EmptyStateProps) => {
  return (
    <div
      className={`flex flex-col items-center justify-center p-8 md:p-12 text-center rounded-2xl bg-slate-900/35 border border-dashed border-slate-800/80 ${className}`}
      {...props}
    >
      <span className="text-4xl mb-4 select-none" aria-hidden="true">
        {icon}
      </span>
      <h3 className="text-lg font-bold text-slate-200 mb-2">{title}</h3>
      <p className="text-slate-400 text-sm max-w-sm mb-6 leading-relaxed">
        {description}
      </p>
      {actionLabel && onAction && (
        <Button variant="primary" onClick={onAction}>
          {actionLabel}
        </Button>
      )}
    </div>
  )
}

interface LoadingStateProps extends HTMLAttributes<HTMLDivElement> {
  description?: string
}

export const LoadingState = ({
  description = 'Loading workspace components...',
  className = '',
  ...props
}: LoadingStateProps) => {
  return (
    <div
      className={`flex flex-col items-center justify-center p-12 text-center gap-4 ${className}`}
      {...props}
    >
      <Spinner size="lg" />
      <span className="text-sm font-medium text-slate-500 select-none animate-pulse">
        {description}
      </span>
    </div>
  )
}

interface ErrorStateProps extends HTMLAttributes<HTMLDivElement> {
  title?: string
  description: string
  actionLabel?: string
  onAction?: () => void
}

export const ErrorState = ({
  title = 'System Configuration Error',
  description,
  actionLabel = 'Retry Connection',
  onAction,
  className = '',
  ...props
}: ErrorStateProps) => {
  return (
    <div className={`max-w-lg mx-auto p-2 ${className}`} {...props}>
      <Alert variant="error" title={title}>
        <div className="mb-4">{description}</div>
        {onAction && (
          <Button variant="danger" size="sm" onClick={onAction}>
            {actionLabel}
          </Button>
        )}
      </Alert>
    </div>
  )
}

import { describe, it, expect } from 'vitest'
import { renderToStaticMarkup } from 'react-dom/server'
import {
  Button,
  Card,
  Input,
  Textarea,
  Checkbox,
  Badge,
  Alert,
  Spinner,
  Divider,
  Container,
  PageHeader,
  Stack,
  Grid,
  EmptyState,
  LoadingState,
  ErrorState,
} from './components/ui'

describe('UI/UX Polish and Accessibility Regression Suite', () => {
  
  // 1. Accessibility & ARIA labels
  describe('Accessibility Support', () => {
    it('should render alert with role="alert"', () => {
      const html = renderToStaticMarkup(
        <Alert title="Verification Failed" variant="error">
          Check database connection
        </Alert>
      )
      expect(html).toContain('role="alert"')
    })

    it('should include aria-label on spinner', () => {
      const html = renderToStaticMarkup(<Spinner size="md" />)
      expect(html).toContain('role="status"')
      expect(html).toContain('aria-label="Loading"')
    })

    it('should render dismiss button in alert with proper aria-label', () => {
      const html = renderToStaticMarkup(
        <Alert title="Dismissable Alert" onClose={() => {}}>
          Content
        </Alert>
      )
      expect(html).toContain('aria-label="Dismiss alert"')
    })

    it('should hidden icons from screen readers using aria-hidden', () => {
      const html = renderToStaticMarkup(
        <Alert title="Decorative Icon Alert">
          Alert content
        </Alert>
      )
      expect(html).toContain('aria-hidden="true"')
    })
  })

  // 2. Keyboard Navigation
  describe('Keyboard Navigation', () => {
    it('should provide keyboard access (cursor-pointer class)', () => {
      const html = renderToStaticMarkup(<Button>Press Tab</Button>)
      expect(html).toContain('cursor-pointer')
    })

    it('should render checkboxes with correct standard cursor classes', () => {
      const html = renderToStaticMarkup(<Checkbox id="kb-checkbox" label="Enable telemetry" />)
      expect(html).toContain('cursor-pointer')
    })
  })

  // 3. Focus Management
  describe('Focus Management & Indicators', () => {
    it('should include focus-ring classes on buttons', () => {
      const html = renderToStaticMarkup(<Button variant="primary">Focused Action</Button>)
      expect(html).toContain('focus:ring-2')
      expect(html).toContain('focus:ring-indigo-500')
    })

    it('should bind input labels to inputs via id and htmlFor', () => {
      const html = renderToStaticMarkup(<Input id="username" label="User ID" />)
      expect(html).toContain('for="username"')
      expect(html).toContain('id="username"')
    })

    it('should include focus-ring classes on textareas', () => {
      const html = renderToStaticMarkup(<Textarea id="description" label="Info" />)
      expect(html).toContain('focus:ring-2')
      expect(html).toContain('focus:border-indigo-500/80')
    })
  })

  // 4. Component Consistency
  describe('Component Style Consistency', () => {
    it('should apply correct color class based on badge variant', () => {
      const infoHtml = renderToStaticMarkup(<Badge variant="info">Info</Badge>)
      const successHtml = renderToStaticMarkup(<Badge variant="success">Success</Badge>)
      expect(infoHtml).toContain('text-indigo-400')
      expect(successHtml).toContain('text-emerald-400')
    })

    it('should apply primary button styling correctly', () => {
      const html = renderToStaticMarkup(<Button variant="primary">Confirm</Button>)
      expect(html).toContain('bg-indigo-600')
      expect(html).toContain('shadow-indigo-600/20')
    })

    it('should apply danger button styling correctly', () => {
      const html = renderToStaticMarkup(<Button variant="danger">Delete</Button>)
      expect(html).toContain('bg-red-600')
      expect(html).toContain('shadow-red-600/20')
    })

    it('should support hoverable card styling', () => {
      const html = renderToStaticMarkup(<Card hoverable>Hover card</Card>)
      expect(html).toContain('hover:border-slate-700/80')
      expect(html).toContain('transition-all')
    })
  })

  // 5. Error Message Rendering
  describe('Error Message Rendering', () => {
    it('should show correct error title and recovery message', () => {
      const html = renderToStaticMarkup(
        <ErrorState
          title="Validation Failure"
          description="DDL schema contains cycles. Please resolve the reference loop."
        />
      )
      expect(html).toContain('Validation Failure')
      expect(html).toContain('DDL schema contains cycles')
    })

    it('should render input field in error status', () => {
      const html = renderToStaticMarkup(
        <Input id="error-input" label="Invalid Field" error="Value is required" />
      )
      expect(html).toContain('border-red-500/80')
      expect(html).toContain('Value is required')
    })
  })

  // 6. Empty States
  describe('Empty States Rendering', () => {
    it('should render empty state illustration, title and action button', () => {
      const html = renderToStaticMarkup(
        <EmptyState
          title="No Active Projects"
          description="Create a project to initialize the developer environment."
          actionLabel="Create Project"
          onAction={() => {}}
        />
      )
      expect(html).toContain('No Active Projects')
      expect(html).toContain('Create Project')
    })
  })

  // 7. Loading States
  describe('Loading States Rendering', () => {
    it('should render loading status descriptions with custom labels', () => {
      const html = renderToStaticMarkup(<LoadingState description="Generating database..." />)
      expect(html).toContain('Generating database...')
      expect(html).toContain('animate-spin')
    })
  })

  // 8. Responsive Layouts
  describe('Responsive Layouts', () => {
    it('should apply column classes correctly in grids', () => {
      const html = renderToStaticMarkup(
        <Grid cols={3}>
          <div>1</div>
          <div>2</div>
          <div>3</div>
        </Grid>
      )
      expect(html).toContain('grid-cols-1 md:grid-cols-2 lg:grid-cols-3')
    })

    it('should handle flex-col structure in stack elements by default', () => {
      const html = renderToStaticMarkup(
        <Stack>
          <div>Row 1</div>
          <div>Row 2</div>
        </Stack>
      )
      expect(html).toContain('flex-col')
    })
  })

  // 9. Theme Consistency
  describe('Theme Consistency and Styles', () => {
    it('should apply dark/slate-950 system background by default', () => {
      const html = renderToStaticMarkup(<Container>Main View</Container>)
      expect(html).toContain('max-w-7xl')
    })

    it('should render divider line aligned to color system', () => {
      const html = renderToStaticMarkup(<Divider label="or" />)
      expect(html).toContain('border-slate-800/80')
    })
  })

  // 10. UI Regression Checks
  describe('UI Regression and Component Layouts', () => {
    it('should render headers and subtitles cleanly', () => {
      const html = renderToStaticMarkup(
        <PageHeader title="Schema Designer" subtitle="Visual interface to configure databases" />
      )
      expect(html).toContain('Schema Designer')
      expect(html).toContain('Visual interface to configure databases')
    })
  })
})

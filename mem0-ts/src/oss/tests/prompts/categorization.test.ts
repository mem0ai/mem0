import { buildCategorizationInput } from '../../src/prompts'

const categories = new Map<string, string>()
categories.set('personal', 'personal info')

describe('categorization#buildCategorizationInput', () => {
  it('returns categorization input', () => {
    const input = buildCategorizationInput('user message', categories)    
    expect(input.length).toBe(2)
    expect(input[0].role).toBe('system')
    expect(input[0].content).toContain('- personal: personal info')
    expect(input[1].role).toBe('user')
    expect(input[1].content).toBe('user message')
  })
})
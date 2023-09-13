import { EmbedChainApp } from '../embedchain';

const mockAdd = jest.fn();
const mockAddLocal = jest.fn();
const mockQuery = jest.fn();

jest.mock('../embedchain', () => {
  return {
    EmbedChainApp: jest.fn().mockImplementation(() => {
      return {
        add: mockAdd,
        addLocal: mockAddLocal,
        query: mockQuery,
      };
    }),
  };
});

describe('Test App', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('tests the App', async () => {
    mockQuery.mockResolvedValue(
      'Naval argues that humans possess the unique capacity to understand explanations or concepts to the maximum extent possible in this physical reality.'
    );

    const navalChatBot = await new EmbedChainApp(undefined, false);

    // Embed Online Resources
    await navalChatBot.add('web_page', 'https://nav.al/feedback');
    await navalChatBot.add('web_page', 'https://nav.al/agi');
    await navalChatBot.add(
      'pdf_file',
      'https://navalmanack.s3.amazonaws.com/Eric-Jorgenson_The-Almanack-of-Naval-Ravikant_Final.pdf'
    );

    // Embed Local Resources
    await navalChatBot.addLocal('qna_pair', [
      'Who is Naval Ravikant?',
      'Naval Ravikant is an Indian-American entrepreneur and investor.',
    ]);

    const result = await navalChatBot.query(
      'What unique capacity does Naval argue humans possess when it comes to understanding explanations or concepts?'
    );

    expect(mockAdd).toHaveBeenCalledWith('web_page', 'https://nav.al/feedback');
    expect(mockAdd).toHaveBeenCalledWith('web_page', 'https://nav.al/agi');
    expect(mockAdd).toHaveBeenCalledWith(
      'pdf_file',
      'https://navalmanack.s3.amazonaws.com/Eric-Jorgenson_The-Almanack-of-Naval-Ravikant_Final.pdf'
    );
    expect(mockAddLocal).toHaveBeenCalledWith('qna_pair', [
      'Who is Naval Ravikant?',
      'Naval Ravikant is an Indian-American entrepreneur and investor.',
    ]);
    expect(mockQuery).toHaveBeenCalledWith(
      'What unique capacity does Naval argue humans possess when it comes to understanding explanations or concepts?'
    );
    expect(result).toBe(
      'Naval argues that humans possess the unique capacity to understand explanations or concepts to the maximum extent possible in this physical reality.'
    );
  });
});

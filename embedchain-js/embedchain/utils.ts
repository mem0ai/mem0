/**
 * This function takes in a string and performs a series of text cleaning operations.
 * @param {str} text: The text to be cleaned. This is expected to be a string.
 * @returns {str}: The cleaned text after all the cleaning operations have been performed.
 */
export function cleanString(text: string): string {
  // Replacement of newline characters:
  let cleanedText = text.replace(/\n/g, ' ');

  // Stripping and reducing multiple spaces to single:
  cleanedText = cleanedText.trim().replace(/\s+/g, ' ');

  // Removing backslashes:
  cleanedText = cleanedText.replace(/\\/g, '');

  // Replacing hash characters:
  cleanedText = cleanedText.replace(/#/g, ' ');

  // Eliminating consecutive non-alphanumeric characters:
  // This regex identifies consecutive non-alphanumeric characters (i.e., not a word character [a-zA-Z0-9_] and not a whitespace) in the string
  // and replaces each group of such characters with a single occurrence of that character.
  // For example, "!!! hello !!!" would become "! hello !".
  cleanedText = cleanedText.replace(/([^\w\s])\1*/g, '$1');

  return cleanedText;
}

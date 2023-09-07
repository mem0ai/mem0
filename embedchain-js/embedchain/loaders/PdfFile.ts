import type { TextContent } from 'pdfjs-dist/types/src/display/api';

import type { LoaderResult, Metadata } from '../models';
import { cleanString } from '../utils';
import { BaseLoader } from './BaseLoader';

const pdfjsLib = require('pdfjs-dist');

interface Page {
  page_content: string;
}

class PdfFileLoader extends BaseLoader {
  static async getPagesFromPdf(url: string): Promise<Page[]> {
    const loadingTask = pdfjsLib.getDocument(url);
    const pdf = await loadingTask.promise;
    const { numPages } = pdf;

    const promises = Array.from({ length: numPages }, async (_, i) => {
      const page = await pdf.getPage(i + 1);
      const pageText: TextContent = await page.getTextContent();
      const pageContent: string = pageText.items
        .map((item) => ('str' in item ? item.str : ''))
        .join(' ');

      return {
        page_content: pageContent,
      };
    });

    return Promise.all(promises);
  }

  // eslint-disable-next-line class-methods-use-this
  async loadData(url: string): Promise<LoaderResult> {
    const pages: Page[] = await PdfFileLoader.getPagesFromPdf(url);
    const output: LoaderResult = [];

    if (!pages.length) {
      throw new Error('No data found');
    }

    pages.forEach((page) => {
      let content: string = page.page_content;
      content = cleanString(content);
      const metaData: Metadata = {
        url,
      };
      output.push({
        content,
        metaData,
      });
    });
    return output;
  }
}

export { PdfFileLoader };

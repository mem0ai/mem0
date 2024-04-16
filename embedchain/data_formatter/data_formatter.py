from importlib import import_module
from typing import Optional

from embedchain.chunkers.base_chunker import BaseChunker
from embedchain.config import AddConfig
from embedchain.config.add_config import ChunkerConfig, LoaderConfig
from embedchain.helpers.json_serializable import JSONSerializable
from embedchain.loaders.base_loader import BaseLoader
from embedchain.models.data_type import DataType


class DataFormatter(JSONSerializable):
    """
    DataFormatter is an internal utility class which abstracts the mapping for
    loaders and chunkers to the data_type entered by the user in their
    .add or .add_local method call
    """

    def __init__(
        self,
        data_type: DataType,
        config: AddConfig,
        loader: Optional[BaseLoader] = None,
        chunker: Optional[BaseChunker] = None,
    ):
        """
        Initialize a dataformatter, set data type and chunker based on datatype.

        :param data_type: The type of the data to load and chunk.
        :type data_type: DataType
        :param config: AddConfig instance with nested loader and chunker config attributes.
        :type config: AddConfig
        """
        self.loader = self._get_loader(data_type=data_type, config=config.loader, loader=loader)
        self.chunker = self._get_chunker(data_type=data_type, config=config.chunker, chunker=chunker)

    @staticmethod
    def _lazy_load(module_path: str):
        module_path, class_name = module_path.rsplit(".", 1)
        module = import_module(module_path)
        return getattr(module, class_name)

    def _get_loader(self, data_type: DataType, config: LoaderConfig, loader: Optional[BaseLoader]) -> BaseLoader:
        """
        Returns the appropriate data loader for the given data type.

        :param data_type: The type of the data to load.
        :type data_type: DataType
        :param config: Config to initialize the loader with.
        :type config: LoaderConfig
        :raises ValueError: If an unsupported data type is provided.
        :return: The loader for the given data type.
        :rtype: BaseLoader
        """
        loaders = {
            DataType.YOUTUBE_VIDEO: "embedchain.loaders.youtube_video.YoutubeVideoLoader",
            DataType.PDF_FILE: "embedchain.loaders.pdf_file.PdfFileLoader",
            DataType.WEB_PAGE: "embedchain.loaders.web_page.WebPageLoader",
            DataType.QNA_PAIR: "embedchain.loaders.local_qna_pair.LocalQnaPairLoader",
            DataType.TEXT: "embedchain.loaders.local_text.LocalTextLoader",
            DataType.DOCX: "embedchain.loaders.docx_file.DocxFileLoader",
            DataType.SITEMAP: "embedchain.loaders.sitemap.SitemapLoader",
            DataType.XML: "embedchain.loaders.xml.XmlLoader",
            DataType.DOCS_SITE: "embedchain.loaders.docs_site_loader.DocsSiteLoader",
            DataType.CSV: "embedchain.loaders.csv.CsvLoader",
            DataType.MDX: "embedchain.loaders.mdx.MdxLoader",
            DataType.IMAGE: "embedchain.loaders.image.ImageLoader",
            DataType.UNSTRUCTURED: "embedchain.loaders.unstructured_file.UnstructuredLoader",
            DataType.JSON: "embedchain.loaders.json.JSONLoader",
            DataType.OPENAPI: "embedchain.loaders.openapi.OpenAPILoader",
            DataType.GMAIL: "embedchain.loaders.gmail.GmailLoader",
            DataType.NOTION: "embedchain.loaders.notion.NotionLoader",
            DataType.SUBSTACK: "embedchain.loaders.substack.SubstackLoader",
            DataType.YOUTUBE_CHANNEL: "embedchain.loaders.youtube_channel.YoutubeChannelLoader",
            DataType.DISCORD: "embedchain.loaders.discord.DiscordLoader",
            DataType.RSSFEED: "embedchain.loaders.rss_feed.RSSFeedLoader",
            DataType.BEEHIIV: "embedchain.loaders.beehiiv.BeehiivLoader",
            DataType.GOOGLE_DRIVE: "embedchain.loaders.google_drive.GoogleDriveLoader",
            DataType.DIRECTORY: "embedchain.loaders.directory_loader.DirectoryLoader",
            DataType.SLACK: "embedchain.loaders.slack.SlackLoader",
            DataType.DROPBOX: "embedchain.loaders.dropbox.DropboxLoader",
            DataType.TEXT_FILE: "embedchain.loaders.text_file.TextFileLoader",
            DataType.EXCEL_FILE: "embedchain.loaders.excel_file.ExcelFileLoader",
        }

        if data_type == DataType.CUSTOM or loader is not None:
            loader_class: type = loader
            if loader_class:
                return loader_class
        elif data_type in loaders:
            loader_class: type = self._lazy_load(loaders[data_type])
            return loader_class()

        raise ValueError(
            f"Cant find the loader for {data_type}.\
                    We recommend to pass the loader to use data_type: {data_type},\
                        check `https://docs.embedchain.ai/data-sources/overview`."
        )

    def _get_chunker(self, data_type: DataType, config: ChunkerConfig, chunker: Optional[BaseChunker]) -> BaseChunker:
        """Returns the appropriate chunker for the given data type (updated for lazy loading)."""
        chunker_classes = {
            DataType.YOUTUBE_VIDEO: "embedchain.chunkers.youtube_video.YoutubeVideoChunker",
            DataType.PDF_FILE: "embedchain.chunkers.pdf_file.PdfFileChunker",
            DataType.WEB_PAGE: "embedchain.chunkers.web_page.WebPageChunker",
            DataType.QNA_PAIR: "embedchain.chunkers.qna_pair.QnaPairChunker",
            DataType.TEXT: "embedchain.chunkers.text.TextChunker",
            DataType.DOCX: "embedchain.chunkers.docx_file.DocxFileChunker",
            DataType.SITEMAP: "embedchain.chunkers.sitemap.SitemapChunker",
            DataType.XML: "embedchain.chunkers.xml.XmlChunker",
            DataType.DOCS_SITE: "embedchain.chunkers.docs_site.DocsSiteChunker",
            DataType.CSV: "embedchain.chunkers.table.TableChunker",
            DataType.MDX: "embedchain.chunkers.mdx.MdxChunker",
            DataType.IMAGE: "embedchain.chunkers.image.ImageChunker",
            DataType.UNSTRUCTURED: "embedchain.chunkers.unstructured_file.UnstructuredFileChunker",
            DataType.JSON: "embedchain.chunkers.json.JSONChunker",
            DataType.OPENAPI: "embedchain.chunkers.openapi.OpenAPIChunker",
            DataType.GMAIL: "embedchain.chunkers.gmail.GmailChunker",
            DataType.NOTION: "embedchain.chunkers.notion.NotionChunker",
            DataType.SUBSTACK: "embedchain.chunkers.substack.SubstackChunker",
            DataType.YOUTUBE_CHANNEL: "embedchain.chunkers.common_chunker.CommonChunker",
            DataType.DISCORD: "embedchain.chunkers.common_chunker.CommonChunker",
            DataType.CUSTOM: "embedchain.chunkers.common_chunker.CommonChunker",
            DataType.RSSFEED: "embedchain.chunkers.rss_feed.RSSFeedChunker",
            DataType.BEEHIIV: "embedchain.chunkers.beehiiv.BeehiivChunker",
            DataType.GOOGLE_DRIVE: "embedchain.chunkers.google_drive.GoogleDriveChunker",
            DataType.DIRECTORY: "embedchain.chunkers.common_chunker.CommonChunker",
            DataType.SLACK: "embedchain.chunkers.common_chunker.CommonChunker",
            DataType.DROPBOX: "embedchain.chunkers.common_chunker.CommonChunker",
            DataType.TEXT_FILE: "embedchain.chunkers.common_chunker.CommonChunker",
            DataType.EXCEL_FILE: "embedchain.chunkers.excel_file.ExcelFileChunker",
        }

        if chunker is not None:
            return chunker
        elif data_type in chunker_classes:
            chunker_class = self._lazy_load(chunker_classes[data_type])
            chunker = chunker_class(config)
            chunker.set_data_type(data_type)
            return chunker

        raise ValueError(
            f"Cant find the chunker for {data_type}.\
                We recommend to pass the chunker to use data_type: {data_type},\
                    check `https://docs.embedchain.ai/data-sources/overview`."
        )

import os
from django.conf import settings
import traceback
from langchain_community.document_loaders import PyPDFLoader, UnstructuredExcelLoader, CSVLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import PGVector
from langchain_openai import OpenAIEmbeddings
from langchain_core.documents import Document


class DocumentProcessor:
    """Production-ready document processor for PDF, CSV, XLSX ingestion into vector database."""
    
    def __init__(self, agent_id: str):
        self.agent_id = agent_id
        self.embedding = OpenAIEmbeddings(
            model=settings.EMBEDDING_MODEL,
            api_key=settings.API_KEY
        )
        self.connection_string = (
            f"postgresql://{settings.POSTGRES_USER}:{settings.POSTGRES_PASSWORD}"
            f"@{settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB_NAME}"
        )
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            length_function=len,
            separators=["\n\n", "\n", " ", ""]
        )
    
    def process_pdf(self, file_path: str) -> dict:
        """
        Extract text from PDF, chunk it, and store in vector database.
        
        Args:
            file_path: Absolute path to PDF file
            
        Returns:
            dict: {"status": "success", "chunks": count, "source": filename}
        """
        try:
            pdf_name = os.path.basename(file_path)
            print(f"📄 Starting PDF processing: {pdf_name}")
            
            # Load PDF
            print(f"📖 Loading PDF from: {file_path}")
            loader = PyPDFLoader(file_path)
            pages = loader.load()
            print(f"✅ Extracted {len(pages)} pages from PDF")
            
            # Split into chunks
            print(f"✂️  Splitting text into chunks...")
            chunks = self.text_splitter.split_documents(pages)
            print(f"✅ Created {len(chunks)} chunks from {len(pages)} pages")
            
            # Add metadata
            for idx, chunk in enumerate(chunks, 1):
                chunk.metadata["agent_id"] = self.agent_id
                chunk.metadata["source"] = pdf_name
                if idx % 10 == 0:
                    print(f"⚙️  Processing chunk {idx}/{len(chunks)}...")
            
            # Store in vector database
            print(f"🔄 Generating embeddings and storing in vector database...")
            PGVector.from_documents(
                documents=chunks,
                embedding=self.embedding,
                collection_name=str(self.agent_id),
                connection_string=self.connection_string,
                pre_delete_collection=False
            )
            print(f"✅ Successfully stored {len(chunks)} chunks in vector database")
            
            return {
                "status": "success",
                "chunks": len(chunks),
                "source": pdf_name
            }
            
        except Exception as e:
            print(f"❌ Error processing PDF: {str(e)}")
            return {
                "status": "failed",
                "error": str(e)
            }
    
    def process_text(self, text: str, source: str, metadata: dict = None) -> dict:
        """
        Process raw text and store in vector database.
        
        Args:
            text: Raw text content
            source: Source identifier (URL, filename, etc.)
            metadata: Additional metadata to store
            
        Returns:
            dict: {"status": "success", "chunks": count, "source": source}
        """
        try:
            print(f"📝 Starting text processing from source: {source}")
            print(f"📏 Text length: {len(text)} characters")
            
            # Create document
            doc = Document(
                page_content=text,
                metadata=metadata or {}
            )
            
            # Split into chunks
            print(f"✂️  Splitting text into chunks...")
            chunks = self.text_splitter.split_documents([doc])
            print(f"✅ Created {len(chunks)} chunks")
            
            # Add metadata
            for chunk in chunks:
                chunk.metadata["agent_id"] = self.agent_id
                if "source" not in chunk.metadata:
                    chunk.metadata["source"] = source
            
            # Store in vector database
            print(f"🔄 Generating embeddings and storing in vector database...")
            PGVector.from_documents(
                documents=chunks,
                embedding=self.embedding,
                collection_name=str(self.agent_id),
                connection_string=self.connection_string,
                pre_delete_collection=False
            )
            print(f"✅ Successfully stored {len(chunks)} chunks in vector database")
            
            return {
                "status": "success",
                "chunks": len(chunks),
                "source": source
            }
            
        except Exception as e:
            print(f"❌ Error processing text: {str(e)}")
            return {
                "status": "failed",
                "error": str(e)
            }
    
    def search(self, query: str, k: int = 3) -> list:
        """
        Semantic search in vector database.
        
        Args:
            query: Search query
            k: Number of results to return
            
        Returns:
            list: List of relevant document chunks
        """
        vector_store = PGVector(
            collection_name=str(self.agent_id),
            connection_string=self.connection_string,
            embedding_function=self.embedding
        )
        
        results = vector_store.similarity_search(
            query,
            k=k,
            filter={"agent_id": self.agent_id}
        )
        
        return "\n\n".join([doc.page_content for doc in results])
    
    def delete_document(self, source: str) -> dict:
        """
        Delete all chunks for a specific document.
        
        Args:
            source: Document source (filename) to delete
            
        Returns:
            dict: {"status": "success", "source": source}
        """
        try:
            vector_store = PGVector(
                collection_name=str(self.agent_id),
                connection_string=self.connection_string,
                embedding_function=self.embedding
            )
            
            # Delete by metadata filter
            vector_store.delete(
                filter={"agent_id": self.agent_id, "source": source}
            )
            
            return {
                "status": "success",
                "source": source
            }
            
        except Exception as e:
            return {
                "status": "failed",
                "error": str(e),
                "source": source
            }
    
    def process_csv(self, file_path: str) -> dict:
        """
        Extract text from CSV using CSVLoader, chunk it, and store in vector database.
        
        Args:
            file_path: Absolute path to CSV file
            
        Returns:
            dict: {"status": "success", "chunks": count, "source": filename}
        """
        try:
            csv_name = os.path.basename(file_path)
            print(f"📊 Starting CSV processing: {csv_name}")
            
            # Load CSV using CSVLoader
            print(f"📋 Loading CSV file...")
            loader = CSVLoader(file_path=file_path, encoding='utf-8')
            documents = loader.load()
            
            print(f"✅ Loaded {len(documents)} rows from CSV")
            
            if not documents:
                print("⚠️ No content extracted from CSV file")
                return {
                    "status": "failed",
                    "error": "No content extracted",
                    "chunks": 0
                }
            
            # Split into chunks
            print(f"✂️  Splitting text into chunks...")
            chunks = self.text_splitter.split_documents(documents)
            print(f"✅ Created {len(chunks)} chunks from {len(documents)} rows")
            
            # Add metadata
            for chunk in chunks:
                chunk.metadata["agent_id"] = self.agent_id
                chunk.metadata["source"] = csv_name
                chunk.metadata["file_type"] = "csv"
            
            # Store in vector database
            print(f"🔄 Generating embeddings and storing in vector database...")
            PGVector.from_documents(
                documents=chunks,
                embedding=self.embedding,
                collection_name=str(self.agent_id),
                connection_string=self.connection_string,
                pre_delete_collection=False
            )
            print(f"✅ Successfully stored {len(chunks)} chunks in vector database")
            
            return {
                "status": "success",
                "chunks": len(chunks),
                "source": csv_name
            }
            
        except Exception as e:
            print(f"❌ Error processing CSV: {str(e)}")
            traceback.print_exc()
            return {
                "status": "failed",
                "error": str(e)
            }
    
    def process_xlsx(self, file_path: str) -> dict:
        """
        Extract text from XLSX/XLS using UnstructuredExcelLoader, chunk it, and store in vector database.
        
        Args:
            file_path: Absolute path to XLSX/XLS file
            
        Returns:
            dict: {"status": "success", "chunks": count, "source": filename}
        """
        try:
            xlsx_name = os.path.basename(file_path)
            print(f"📊 Starting XLSX processing: {xlsx_name}")
            
            # Load Excel file using UnstructuredExcelLoader
            print(f"📋 Loading Excel file...")
            loader = UnstructuredExcelLoader(file_path, mode="elements")
            documents = loader.load()
            
            print(f"✅ Loaded {len(documents)} elements from Excel file")
            
            # Combine all document content
            combined_text = "\n\n".join([doc.page_content for doc in documents if doc.page_content.strip()])
            
            if not combined_text.strip():
                print("⚠️ No content extracted from Excel file")
                return {
                    "status": "failed",
                    "error": "No content extracted",
                    "chunks": 0
                }
            
            # Create document with combined content
            doc = Document(
                page_content=combined_text,
                metadata={"source": xlsx_name, "file_type": "xlsx"}
            )
            
            # Split into chunks
            print(f"✂️  Splitting text into chunks...")
            chunks = self.text_splitter.split_documents([doc])
            print(f"✅ Created {len(chunks)} chunks")
            
            # Add metadata
            for chunk in chunks:
                chunk.metadata["agent_id"] = self.agent_id
                chunk.metadata["source"] = xlsx_name
            
            # Store in vector database
            print(f"🔄 Generating embeddings and storing in vector database...")
            PGVector.from_documents(
                documents=chunks,
                embedding=self.embedding,
                collection_name=str(self.agent_id),
                connection_string=self.connection_string,
                pre_delete_collection=False
            )
            print(f"✅ Successfully stored {len(chunks)} chunks in vector database")
            
            return {
                "status": "success",
                "chunks": len(chunks),
                "source": xlsx_name
            }
            
        except Exception as e:
            print(f"❌ Error processing XLSX: {str(e)}")
            traceback.print_exc()
            return {
                "status": "failed",
                "error": str(e)
            }
    
    def delete_agent_vectors(self) -> dict:
        """
        Delete all vector embeddings for this agent.
        
        Returns:
            dict: {"status": "success", "agent_id": agent_id}
        """
        try:
            print(f"🗑️  Deleting all vectors for agent: {self.agent_id}")
            vector_store = PGVector(
                collection_name=str(self.agent_id),
                connection_string=self.connection_string,
                embedding_function=self.embedding
            )
            
            # Delete all vectors for this agent
            vector_store.delete(
                filter={"agent_id": self.agent_id}
            )
            
            print(f"✅ Successfully deleted all vectors for agent: {self.agent_id}")
            return {
                "status": "success",
                "agent_id": self.agent_id
            }
            
        except Exception as e:
            print(f"❌ Error deleting vectors for agent {self.agent_id}: {str(e)}")
            return {
                "status": "failed",
                "error": str(e),
                "agent_id": self.agent_id
            }

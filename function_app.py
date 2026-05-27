import logging
import os
import azure.functions as func
from azure.storage.blob import BlobServiceClient
from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.core.credentials import AzureKeyCredential
from openai import AzureOpenAI

# Import the schema we defined above
from models import TranslatedInvoiceOutput

app = func.FunctionApp()

@app.blob_trigger(
    arg_name="myblob", 
    path="input-containerc/{name}.pdf", 
    connection="AzureWebJobsStorage"
)
def agent_blob_reader_chinese_to_eng(myblob: func.InputStream):
    logging.info(f"Agent triggered by Chinese Document: {myblob.name}")

    # Read the raw Chinese PDF file stream
    pdf_bytes = myblob.read()
    
    try:
        # --- PHASE A: OCR Extraction (Handles Multi-lingual Text Layers) ---
        doc_intel_client = DocumentIntelligenceClient(
            endpoint=os.environ["DOCUMENT_INTELLIGENCE_ENDPOINT"],
            credential=AzureKeyCredential(os.environ["DOCUMENT_INTELLIGENCE_KEY"])
        )
        
        # 'prebuilt-layout' handles text extraction for Chinese seamlessly
        poller = doc_intel_client.begin_analyze_document(
            "prebuilt-layout", 
            
            body=pdf_bytes,
            content_type="application/pdf"
        )
        result = poller.result()
        
        # Reconstruct layout text
        extracted_chinese_text = ""
        if result.pages:
            for page in result.pages:
                for line in page.lines:
                    extracted_chinese_text += line.content + "\n"

        logging.info("Phase A complete: Multi-lingual OCR text successfully extracted.")

        # --- PHASE B: Translation & Structured Mapping Agent ---
        openai_client = AzureOpenAI(
            azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
            api_key=os.environ["AZURE_OPENAI_API_KEY"],
            api_version="2024-08-01-preview"
        )

        # Prompt instructs the agent to act as a translator and structural parser
        system_instruction = (
            "You are an expert bilingual financial intelligence agent fluent in Mandarin Chinese and English. "
            "Your objective is to review raw extracted Chinese text from financial invoices, translate all values "
            "and business names into clear professional English, and format them strictly according to the requested JSON schema."
        )

        completion = openai_client.beta.chat.completions.parse(
            model=os.environ["AZURE_OPENAI_DEPLOYMENT"],
            messages=[
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": f"Translate and extract from this text:\n{extracted_chinese_text}"}
            ],
            response_format=TranslatedInvoiceOutput, # Forces output to match our English Pydantic schema
        )

        # Safely extract the translated, structured data object
        structured_english_obj = completion.choices[0].message.parsed
        final_json_payload = structured_english_obj.model_dump_json(indent=4)

        logging.info("Phase B complete: Document successfully translated and mapped to English JSON.")

        # --- PHASE C: Commit to Output Directory ---
        blob_service_client = BlobServiceClient.from_connection_string(os.environ["SourceBlobConnectionString"])
        
        # Replace .pdf extension with an explicit signifier, e.g., _translated.json
        base_filename = os.path.basename(myblob.name).replace(".pdf", "_translated.json")
        
        output_blob_client = blob_service_client.get_blob_client(
            container="output-data", 
            blob=base_filename
        )
        
        output_blob_client.upload_blob(final_json_payload, overwrite=True)
        logging.info(f"Phase C complete: Saved translated English payload to output-directory/{base_filename}")

    except Exception as error:
        logging.error(f"Error within Translation Pipeline: {str(error)}")
        raise error
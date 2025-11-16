"""
settings.py
This module defines a `Settings` dataclass that centralizes configuration
parameters for the Speech-to-Text (STT) and Chat services. It loads values.
"""

import os
from dataclasses import dataclass

@dataclass(frozen=True)
class Settings:
    # STT server + model
    TRANSCRIBE_URL: str = os.getenv("TRANSCRIBE_URL", "http://192.168.0.154:8000/v1/audio/transcriptions")
    MODEL_ID: str = os.getenv("MODEL_ID", "mistralai/Voxtral-Small-24B-2507")

    # Chunking behavior
    N_CHUNKS: int = int(os.getenv("N_CHUNKS", "4"))
    BUFFER_SEC: float = float(os.getenv("BUFFER_SEC", "2.0"))

    # STT parameters
    TEMPERATURE: float = float(os.getenv("TEMPERATURE", "0.0"))
    TOP_P: float = float(os.getenv("TOP_P", "0.1"))
    REPETITIONS_PENALTY: float = float(os.getenv("REPETITIONS_PENALTY", "1.15"))
    FREQUENCY_PENALTY: float = float(os.getenv("FREQUENCY_PENALTY", "0.4"))
    RETRIES: int = int(os.getenv("RETRIES", "2"))

    # Chat parameters
    CHAT_API_BASE = "http://192.168.0.154:8000/v1/chat/completions"  
    CHAT_MODEL_ID = "mistralai/Voxtral-Small-24B-2507"

    # Timeouts
    HTTP_TIMEOUT_SEC: int = int(os.getenv("HTTP_TIMEOUT_SEC", "300"))


    # Health check
    HEALTH_CHECK_URL: str = os.getenv("HEALTH_CHECK_URL","http://192.168.0.154:8000/health")
    HEALTH_CHECK_METHOD: str = os.getenv("HEALTH_CHECK_METHOD", "GET")
    HEALTH_CHECK_EXPECTED_STATUS: int = int(os.getenv("HEALTH_CHECK_EXPECTED_STATUS", "200"))
    HEALTH_CHECK_TIMEOUT_SEC: float = float(os.getenv("HEALTH_CHECK_TIMEOUT_SEC", "5.0"))

    # Backoff to wait if STT is down (8 minutes)
    HEALTH_BACKOFF_SEC: int = int(os.getenv("HEALTH_BACKOFF_SEC", "420"))

    # QA questions

    INTRODUCTION_AND_OPENING = (
    """
    Task:You are given a verified call center conversation between an agent and a customer.Your goal is to *objectively evaluate* the agent’s **introduction and opening** section based strictly on the evidence available in the audio and answer the questions listed below.

    Questions:

      1. **Response Time**
         Question: Identify who spoke first (agent or customer).
         - State whether the *agent* responded in less than 5 seconds from the moment *customer* first started speaking?

      2. **Self-Introduction and Company Name**
         Question: Did the agent mention their *name* (first or last) and *company name* they are affiliated with?
         - Example: This side "Kedar Chitri"(agent name), I am calling from "Thomas Cook India"(company name).
         - Example: "Babita"(agent name) this side from "Thomas Cook India"(company name).
         - Example: Hello, this is "Rahul"(agent name) from "SOTC Holidays"(company name) how may I assist you today?
         - Example: Thanks for calling in Thomas Cook India. Yaminidhi this side, how may I assist you?
         - Example: वेरी गुड आफ्टरनून, ओवैस बोल रहा हूँ, थॉमस कुक से।
         - Example: वेरी गुड आफ्टरनून, दिस इज़ सफाना फ्रॉम थॉमस कुक।

      3. **Purpose of Call**
         Question: What was the reason that the agent stated for reaching out the customer?
         - Purpose can be discussion about a travel plan or an inquiry request made by the customer.
      
    Evluation Criteria:
      1. **Evidence**
         - Provide short, direct quotes from the conversation that support each observation.

    Output Format Rules:
      - Provide your final answer as a single continuous paragraph in plain text.
      - Do not use bullet points, markdown, backslashes (“\”), or newline characters (“\\n”).
      - Strictly Use **Question Type** before answering each question. Example: **Response Time**, **Self-Introduction and Company Name**, **Purpose of Call**.
      - Keep the explanation concise and factual and strictly answer all 3 questions.
   """
)


    PACKAGE_DISCUSSION_QUESTION_PART1 = (
      """
         Task:You are given a verified call center conversation between an agent and a customer.Your objective is to objectively evaluate the agent’s communication quality and answer the questions listed below.

         Questions:

            1. **Package Mention**: Did the agent clearly describe one or more travel packages (e.g., package type, name, or price range)?

            2. **Traveller Details**: 
               - Did the agent confirm the name of the traveller?
               - Did the agent confirm the number of travellers (adults/children)?
               - Did the agent confirm the customer's email id?

            3. **Destination**:
               - Did the agent confirm the destination city/country?
               - Did the agent confirm specific places to cover within the trip?
               
         Evluation Criteria:
               1. **Evidence**
                  - Provide short, direct quotes from the conversation that support each observation.

            Output Format Rules:
            - Provide your final answer as a single continuous paragraph in plain text.
            - Do not use bullet points, markdown, backslashes (“\”), or newline characters (“\\n”).
            - Use **Question Type** before answering each question. Example: **Package Mention**, **Traveller Details**, **Destination**.
            - Keep the explanation concise and factual
      """
   )

    PACKAGE_DISCUSSION_QUESTION_PART2 = (
      """
         Task:You are given a verified call center conversation between an agent and a customer.Your objective is to objectively evaluate the agent’s communication quality and answer the questions listed below.

         Questions:
               
            1. **Tour Type**: Did the agent clarify whether the customer is interested in a group tour or a customized package?

            2. **Travel Dates**: Did the agent confirm the intended dates or month of travel?

            3. **Duration**: Did the agent confirm the total number of days to spend on the trip?

            4. **Departure Details**: Did the agent confirm the departure city or hub?

            
         Evluation Criteria:
               **Evidence**: Provide short, direct quotes from the conversation that support each observation.

            Output Format Rules:
            - Provide your final answer as a single continuous paragraph in plain text.
            - Do not use bullet points, markdown, backslashes (“\”), or newline characters (“\\n”).
            - Use **Question Type** before answering each question. Example: **Tour ype**, **Travel Dates & Duration*.
            - Keep the explanation concise and factual
      """
   )


    PACKAGE_DISCUSSION_QUESTION_PART3 = (
      """
         Task:You are given a verified call center conversation between an agent and a customer.Your objective is to objectively evaluate the agent’s communication quality and answer the questions listed below.

         Questions:

            1. **Occasion**: Did the agent ask about the occasion of travel (e.g., honeymoon, family trip, business, celebration)?
                 
            2. **Budget**: Did the agent confirm the customer’s budget, if required?

            3. **Inclusions & Exclusions**: Did the agent clearly outline inclusions (flights, hotels, meals, transport, activities) and exclusions (visa, insurance, optional tours, personal expenses)?

            4. **Passport and PAN**: Did the agent confirm the availability of valid passport and PAN for all the adult travellers?

            Evluation Criteria:
               **Evidence**: Provide short, direct quotes from the conversation that support each observation.

            Output Format Rules:
            - Provide your final answer as a single continuous paragraph in plain text.
            - Do not use bullet points, markdown, backslashes (“\”), or newline characters (“\\n”).
            - Use **Question Type** before answering each question. Example: **Departure Details**, **Occasion & Budget**, **Inclusions & Exclusions**, **Passport and PAN**.
            - Keep the explanation concise and factual
      """
   )



    AGENT_BEHAVIOR_QUESTION_PART1 = (
      """
      Task:You are given a verified call center conversation between an agent and a customer. Your objective is to objectively evaluate the agent's behavior and communication quality and answer the questions listed below.

      Questions:

         1. **Active Listening and Interruptions**: Did the agent allow the customer to finish speaking without interruption?

         2. **Acknowledgment**: Did the agent acknowledge and validate the customer's statements or concerns and understand the customer's needs?

         3. **Paraphrasing**: Did the agent restate or summarize the customer's needs or preferences accurately to confirm understanding and avoid ambiguities?
         
      Evluation Criteria:

         **Evidence**: Provide short, direct quotes from the conversation that support each observation.

      Output Format Rules:
         - Provide your final answer as a single continuous paragraph in plain text.
         - Do not use bullet points, markdown, backslashes (“\”), or newline characters (“\\n”).
         - Use **Question Type** before answering each question. Example: **Active Listening and Interruptions**, **Acknowledgment**, **Paraphrasing**.
         - Strictly refrain from adding any external web links. Eg. (https://www.youtube.com/watch?v=80vzJqxZ97g&t=46s)
         - Keep the explanation concise and factual
      """
   )

    AGENT_BEHAVIOR_QUESTION_PART2 = (
      """
      Task:You are given a verified call center conversation between an agent and a customer. Your objective is to objectively evaluate the agent's behavior and communication quality and answer the questions listed below.

      Questions:
            
         1. **Confidence and Enthusiasm**: Did the agent's language convey confidence and enthusiasm in the call?
            
         2. **Professionalism in Tone and Language**: Did the agent use polite, respectful, and professional language and tone? Did the agent avoid rudeness, impatience, or unprofessional behavior?


      Evluation Criteria:

         **Evidence**: Provide short, direct quotes from the conversation that support each observation.

      Output Format Rules:
         - Provide your final answer as a single continuous paragraph in plain text.
         - Do not use bullet points, markdown, backslashes (“\”), or newline characters (“\\n”).
         - Use **Question Type** before answering each question. Example: **Confidence and Enthusiasm**, **Professionalism in Tone and Language**.
         - Keep the explanation concise and factual
         - Strictly refrain from adding any external web links. Eg: (https://www.youtube.com/watch?v=80vzJqxZ97g&t=46s)
      """
   )



    CLOSURE = (
      """
      Task: You are given a verified call center conversation between an agent and a customer. Your task is to objectively evaluate how the agent concluded the call, focusing only on what is explicitly said in the conversation and answer the questions listed below.

      Questions:

         1. **Call Closure and Final Assistance**: Did the agent properly close the call by asking if the customer needed any further help?
            
         2. **Survey/Rating**: Did the agent inform the customer about any post-call feedback, rating, or survey link that the customer would be receiving after the call ends?
         
      Evluation Criteria:

         **Evidence**: Provide short, direct quotes from the conversation that support each observation.

      Output Format Rules:
         - Present the entire response as one continuous paragraph in plain text.
         - Do not use bullet points, markdown, backslashes (“\”), or newline characters (“\\n”).
         - Use **Question Type** before answering each question. Example: **Call Closure and Final Assistance**, **Survey/Rating**.
         - Keep the explanation concise and factual.
      """
   )


    PRODUCT_OBJECTION_HANDLING = (
      """
      Task:You are given a verified call center conversation between a travel agent and a customer. Objectively evaluate how the agent handled customer objections about the discussed travel packages and answer the questions listed below.

      Definition (use these to decide what counts as an objection): An objection is a direct concern, hesitation, or disagreement expressed by the customer about price, dates, inclusions/exclusions, brand, itinerary, availability, policies (visa/insurance/refunds), or suitability (group vs. custom).
      

      Questions:
         1. **Objection Presence and Type**: Did the customer raise any objection about the product offered by the agent?.

         2. **Agent Handling Technique**: Identify how the agent responded: clarify(asks questions), evidence/assurance (facts, policies), alternative offer (different package/date/hotel), concession (discount/upgrade), deferral (will check and revert), or no handling observed.

      Evluation Criteria:

         **Evidence**: Provide short, direct quotes from the conversation that support each observation.

      Output Format Rules:
         - Present the entire response as one continuous paragraph in plain text.
         - Do not use bullet points, markdown, backslashes (“\”), or newline characters (“\\n”).
         - Use **Question Type** before answering each question. Example: **Objection Presence and Type**, **Agent Handling Technique**.
         - Keep the explanation concise and factual.
      """
   )


class ModelAnswerService:
    async def get_by_problem(self, problem_id: str):
        pass

    async def update(self, problem_id: str, text: str):
        pass

    async def run_ocr(self, problem_id: str) -> str:
        """OCR 비동기 job을 생성하고 job_id를 반환한다."""
        pass

    async def confirm(self, problem_id: str):
        pass

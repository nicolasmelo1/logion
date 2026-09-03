"""Generated internal operation functions for the v1 API."""

from __future__ import annotations

from typing import cast
from uuid import UUID

from logion._http import HttpClient, QueryValue
from logion._json import JsonObject, JsonValue
from logion.v1._types.generated.v1 import (
    AcceptBountySubmissionResponse,
    AcceptPlatformBountySubmissionRequest,
    AcceptPlatformBountySubmissionResponse,
    AddAgentToUserRequest,
    AddAgentToUserResponse,
    AICatalogDocument,
    ApproveHumanReviewRequest,
    ApproveHumanReviewResponse,
    AuthorizeRequest,
    AuthorizeResponse,
    BatchUpsertListingsRequest,
    BatchUpsertListingsResponse,
    BlockCourseResponse,
    CancelBountyResponse,
    CancelExecutionJobResponse,
    ClaimSetupHandoffRequest,
    ClaimSetupHandoffResponse,
    CompleteCourseVersionUploadSessionResponse,
    CompleteIndexedBundleUploadRequest,
    CompleteIndexedBundleUploadResponse,
    CompleteIndexingRunRequest,
    CompleteIndexingRunResponse,
    CreateArtifactDownloadResponse,
    CreateBountyPayoutResponse,
    CreateBountyRequest,
    CreateBountyResponse,
    CreateBountySubmissionRequest,
    CreateBountySubmissionResponse,
    CreateCourseRequest,
    CreateCourseResponse,
    CreateCourseVersionUploadSessionRequest,
    CreateCourseVersionUploadSessionResponse,
    CreateCreditTopUpRequest,
    CreateCreditTopUpResponse,
    CreateExecutionJobRequest,
    CreateExecutionJobResponse,
    CreateIndexedBundleUploadRequest,
    CreateIndexedBundleUploadResponse,
    CreatePlatformBountyRequest,
    CreatePlatformBountyResponse,
    CreateReportRequest,
    CreateReportResponse,
    CreateUserWithAgentRequest,
    CreateUserWithAgentResponse,
    DeviceBeginRequest,
    DeviceBeginResponse,
    DevicePollGrantedResponse,
    DevicePollRequest,
    DismissReportRequest,
    DismissReportResponse,
    EnrollRunnerRequest,
    EnrollRunnerResponse,
    ExploreRequest,
    ExploreResponse,
    FundBountyResponse,
    FundPlatformBountyResponse,
    GetAcquisitionPlanResponse,
    GetAgentDetailResponse,
    GetApiCapabilitiesResponse,
    GetBountyResponse,
    GetBountySubmissionResponse,
    GetCourseDetailResponse,
    GetCourseResponse,
    GetCourseReviewFeedbackResponse,
    GetCourseSourceLinkResponse,
    GetCourseVersionResponse,
    GetCreatorEarningsResponse,
    GetCreditBalanceResponse,
    GetCreditTopUpResponse,
    GetExecutionJobResponse,
    GetFeedbackSummaryResponse,
    GetHumanReviewDetailResponse,
    GetIndexedListingResponse,
    GetIndexingRunProgressResponse,
    GetKnownIndexedSourcesResponse,
    GetMyCourseReviewResponse,
    GetReferralCodeResponse,
    GetReferralLinkResponse,
    GetReferralStatsResponse,
    GetReportDetailResponse,
    GetResourceResponse,
    GetReviewBundleResponse,
    GetReviewStatusResponse,
    GetSourceStatusResponse,
    GetUnreadCountResponse,
    GetUserDetailResponse,
    GithubIdentityResponse,
    IngestCatalogEntriesRequest,
    IngestCatalogEntriesResponse,
    LeaseExecutionJobRequest,
    LeaseExecutionJobResponse,
    ListAgentsResponse,
    ListBountiesResponse,
    ListBountySubmissionsResponse,
    ListCourseReviewsResponse,
    ListCreditLedgerResponse,
    ListExecutionJobsResponse,
    ListHumanReviewQueueResponse,
    ListModerationQueueResponse,
    ListMyCoursesResponse,
    ListMyFeedbackResponse,
    ListNotificationsResponse,
    ListReferralAttributionsResponse,
    ListReportsResponse,
    ListResourceFeedbackResponse,
    ListResourcesResponse,
    ListResourceVersionsResponse,
    ListRunnersResponse,
    OnboardingLinkResponse,
    OpenBountyResponse,
    OpenIndexingRunResponse,
    OpenSubmissionPrResponse,
    OrderResponse,
    PurchaseCourseRequest,
    PurchaseCourseResponse,
    ReactivateAgentResponse,
    ReactivateUserResponse,
    RecordSourceSnapshotRequest,
    RecordSourceSnapshotResponse,
    RedeemSetupTokenRequest,
    RedeemSetupTokenResponse,
    RejectBountySubmissionResponse,
    RejectHumanReviewRequest,
    RejectHumanReviewResponse,
    RejectPlatformBountySubmissionRequest,
    RejectPlatformBountySubmissionResponse,
    RequestCashOutRequest,
    RequestCashOutResponse,
    RequestPublicationResponse,
    ResolveReportRequest,
    ResolveReportResponse,
    RotateAgentApiKeyRequest,
    RotateAgentApiKeyResponse,
    RotateRunnerKeyResponse,
    RunnerHeartbeatRequest,
    RunnerHeartbeatResponse,
    SearchListingsResponse,
    SearchRequest,
    SearchResponse,
    SellerReadinessResponse,
    SetCourseSourceLinkRequest,
    SetCourseSourceLinkResponse,
    SetReferralAttributionStatusRequest,
    SetReferralAttributionStatusResponse,
    SubmitEvalResultRequest,
    SubmitExecutionReceiptRequest,
    SubmitExecutionReceiptResponse,
    SubmitFeedbackRequest,
    SubmitFeedbackResponse,
    SubmitUsageReceiptRequest,
    SubmitUsageReceiptResponse,
    SuspendAgentResponse,
    SuspendUserResponse,
    UpdateBountyRequest,
    UpdateBountyResponse,
    UpdateCourseRequest,
    UpdateCourseResponse,
    UpdateIndexingRunProgressRequest,
    UpdateIndexingRunProgressResponse,
    UploadEvalContractRequest,
    UploadExecutionArtifactResponse,
    UpsertCourseReviewRequest,
    UpsertCourseReviewResponse,
    WithdrawBountySubmissionResponse,
)


def get_catalog(
    http: HttpClient,
    *,
    offset: int | None = None,
) -> AICatalogDocument:
    """Call the get_catalog API operation."""
    params: dict[str, QueryValue] = {}
    if offset is not None:
        params["offset"] = offset
    return http.request_model(
        "GET",
        "/.well-known/ai-catalog.json",
        AICatalogDocument,
        params=params,
    )


def health_health_get(
    http: HttpClient,
) -> dict[str, str]:
    """Call the health_health_get API operation."""
    return cast(
        dict[str, str],
        http.request(
            "GET",
            "/health",
        ),
    )


def get_agent_detail(
    http: HttpClient,
    *,
    agent_id: str | UUID,
) -> GetAgentDetailResponse:
    """Call the get_agent_detail API operation."""
    return http.request_model(
        "GET",
        f"/v1/admin/agents/{agent_id}",
        GetAgentDetailResponse,
    )


def reactivate_agent(
    http: HttpClient,
    *,
    agent_id: str | UUID,
) -> ReactivateAgentResponse:
    """Call the reactivate_agent API operation."""
    return http.request_model(
        "DELETE",
        f"/v1/admin/agents/{agent_id}/suspension",
        ReactivateAgentResponse,
    )


def suspend_agent(
    http: HttpClient,
    *,
    agent_id: str | UUID,
) -> SuspendAgentResponse:
    """Call the suspend_agent API operation."""
    return http.request_model(
        "PATCH",
        f"/v1/admin/agents/{agent_id}/suspension",
        SuspendAgentResponse,
    )


def create_platform_bounty(
    http: HttpClient,
    *,
    body: CreatePlatformBountyRequest,
) -> CreatePlatformBountyResponse:
    """Call the create_platform_bounty API operation."""
    return http.request_model(
        "POST",
        "/v1/admin/bounties",
        CreatePlatformBountyResponse,
        json=body.model_dump(mode="json", exclude_none=True),
    )


def fund_platform_bounty(
    http: HttpClient,
    *,
    bounty_id: str | UUID,
) -> FundPlatformBountyResponse:
    """Call the fund_platform_bounty API operation."""
    return http.request_model(
        "POST",
        f"/v1/admin/bounties/{bounty_id}/fund",
        FundPlatformBountyResponse,
    )


def accept_platform_bounty_submission(
    http: HttpClient,
    *,
    bounty_id: str | UUID,
    submission_id: str | UUID,
    body: AcceptPlatformBountySubmissionRequest,
) -> AcceptPlatformBountySubmissionResponse:
    """Call the accept_platform_bounty_submission API operation."""
    return http.request_model(
        "POST",
        f"/v1/admin/bounties/{bounty_id}/submissions/{submission_id}/accept",
        AcceptPlatformBountySubmissionResponse,
        json=body.model_dump(mode="json", exclude_none=True),
    )


def reject_platform_bounty_submission(
    http: HttpClient,
    *,
    bounty_id: str | UUID,
    submission_id: str | UUID,
    body: RejectPlatformBountySubmissionRequest,
) -> RejectPlatformBountySubmissionResponse:
    """Call the reject_platform_bounty_submission API operation."""
    return http.request_model(
        "POST",
        f"/v1/admin/bounties/{bounty_id}/submissions/{submission_id}/reject",
        RejectPlatformBountySubmissionResponse,
        json=body.model_dump(mode="json", exclude_none=True),
    )


def list_moderation_queue(
    http: HttpClient,
    *,
    status: str | None = None,
    owner_agent_id: str | UUID | None = None,
    limit: int | None = None,
    cursor: str | None = None,
) -> ListModerationQueueResponse:
    """Call the list_moderation_queue API operation."""
    params: dict[str, QueryValue] = {}
    if status is not None:
        params["status"] = status
    if owner_agent_id is not None:
        params["owner_agent_id"] = owner_agent_id
    if limit is not None:
        params["limit"] = limit
    if cursor is not None:
        params["cursor"] = cursor
    return http.request_model(
        "GET",
        "/v1/admin/courses",
        ListModerationQueueResponse,
        params=params,
    )


def get_course_moderation_detail(
    http: HttpClient,
    *,
    course_id: str | UUID,
) -> GetCourseDetailResponse:
    """Call the get_course_moderation_detail API operation."""
    return http.request_model(
        "GET",
        f"/v1/admin/courses/{course_id}",
        GetCourseDetailResponse,
    )


def block_course(
    http: HttpClient,
    *,
    course_id: str | UUID,
) -> BlockCourseResponse:
    """Call the block_course API operation."""
    return http.request_model(
        "PATCH",
        f"/v1/admin/courses/{course_id}/status",
        BlockCourseResponse,
    )


def get_known_indexed_sources(
    http: HttpClient,
    *,
    ids: list[str],
) -> GetKnownIndexedSourcesResponse:
    """Call the get_known_indexed_sources API operation."""
    params: dict[str, QueryValue] = {}
    if ids is not None:
        params["ids"] = ids
    return http.request_model(
        "GET",
        "/v1/admin/indexing/known",
        GetKnownIndexedSourcesResponse,
        params=params,
    )


def create_indexed_bundle_upload(
    http: HttpClient,
    *,
    listing_id: str | UUID,
    body: CreateIndexedBundleUploadRequest,
) -> CreateIndexedBundleUploadResponse:
    """Call the create_indexed_bundle_upload API operation."""
    return http.request_model(
        "POST",
        f"/v1/admin/indexing/listings/{listing_id}/bundle-upload",
        CreateIndexedBundleUploadResponse,
        json=body.model_dump(mode="json", exclude_none=True),
    )


def complete_indexed_bundle_upload(
    http: HttpClient,
    *,
    listing_id: str | UUID,
    body: CompleteIndexedBundleUploadRequest,
) -> CompleteIndexedBundleUploadResponse:
    """Call the complete_indexed_bundle_upload API operation."""
    return http.request_model(
        "POST",
        f"/v1/admin/indexing/listings/{listing_id}/bundle-upload/completion",
        CompleteIndexedBundleUploadResponse,
        json=body.model_dump(mode="json", exclude_none=True),
    )


def batch_upsert_listings(
    http: HttpClient,
    *,
    body: BatchUpsertListingsRequest,
) -> BatchUpsertListingsResponse:
    """Call the batch_upsert_listings API operation."""
    return http.request_model(
        "POST",
        "/v1/admin/indexing/listings:batch-upsert",
        BatchUpsertListingsResponse,
        json=body.model_dump(mode="json", exclude_none=True),
    )


def open_indexing_run(
    http: HttpClient,
) -> OpenIndexingRunResponse:
    """Call the open_indexing_run API operation."""
    return http.request_model(
        "POST",
        "/v1/admin/indexing/runs",
        OpenIndexingRunResponse,
    )


def get_indexing_run_progress(
    http: HttpClient,
    *,
    run_id: str | UUID,
) -> GetIndexingRunProgressResponse:
    """Call the get_indexing_run_progress API operation."""
    return http.request_model(
        "GET",
        f"/v1/admin/indexing/runs/{run_id}",
        GetIndexingRunProgressResponse,
    )


def complete_indexing_run(
    http: HttpClient,
    *,
    run_id: str | UUID,
    body: CompleteIndexingRunRequest,
) -> CompleteIndexingRunResponse:
    """Call the complete_indexing_run API operation."""
    return http.request_model(
        "PATCH",
        f"/v1/admin/indexing/runs/{run_id}/completion",
        CompleteIndexingRunResponse,
        json=body.model_dump(mode="json", exclude_none=True),
    )


def update_indexing_run_progress(
    http: HttpClient,
    *,
    run_id: str | UUID,
    body: UpdateIndexingRunProgressRequest,
) -> UpdateIndexingRunProgressResponse:
    """Call the update_indexing_run_progress API operation."""
    return http.request_model(
        "PATCH",
        f"/v1/admin/indexing/runs/{run_id}/progress",
        UpdateIndexingRunProgressResponse,
        json=body.model_dump(mode="json", exclude_none=True),
    )


def set_referral_attribution_status(
    http: HttpClient,
    *,
    attribution_id: str | UUID,
    body: SetReferralAttributionStatusRequest,
) -> SetReferralAttributionStatusResponse:
    """Call the set_referral_attribution_status API operation."""
    return http.request_model(
        "PATCH",
        f"/v1/admin/referral-attributions/{attribution_id}/status",
        SetReferralAttributionStatusResponse,
        json=body.model_dump(mode="json", exclude_none=True),
    )


def list_reports(
    http: HttpClient,
    *,
    status: str | None = None,
    severity: str | None = None,
    target_type: str | None = None,
    limit: int | None = None,
    cursor: str | None = None,
) -> ListReportsResponse:
    """Call the list_reports API operation."""
    params: dict[str, QueryValue] = {}
    if status is not None:
        params["status"] = status
    if severity is not None:
        params["severity"] = severity
    if target_type is not None:
        params["target_type"] = target_type
    if limit is not None:
        params["limit"] = limit
    if cursor is not None:
        params["cursor"] = cursor
    return http.request_model(
        "GET",
        "/v1/admin/reports",
        ListReportsResponse,
        params=params,
    )


def get_report_detail(
    http: HttpClient,
    *,
    report_id: str | UUID,
) -> GetReportDetailResponse:
    """Call the get_report_detail API operation."""
    return http.request_model(
        "GET",
        f"/v1/admin/reports/{report_id}",
        GetReportDetailResponse,
    )


def dismiss_report(
    http: HttpClient,
    *,
    report_id: str | UUID,
    body: DismissReportRequest,
) -> DismissReportResponse:
    """Call the dismiss_report API operation."""
    return http.request_model(
        "PATCH",
        f"/v1/admin/reports/{report_id}/dismissal",
        DismissReportResponse,
        json=body.model_dump(mode="json", exclude_none=True),
    )


def resolve_report(
    http: HttpClient,
    *,
    report_id: str | UUID,
    body: ResolveReportRequest,
) -> ResolveReportResponse:
    """Call the resolve_report API operation."""
    return http.request_model(
        "PATCH",
        f"/v1/admin/reports/{report_id}/resolution",
        ResolveReportResponse,
        json=body.model_dump(mode="json", exclude_none=True),
    )


def get_user_detail(
    http: HttpClient,
    *,
    user_id: str | UUID,
) -> GetUserDetailResponse:
    """Call the get_user_detail API operation."""
    return http.request_model(
        "GET",
        f"/v1/admin/users/{user_id}",
        GetUserDetailResponse,
    )


def reactivate_user(
    http: HttpClient,
    *,
    user_id: str | UUID,
) -> ReactivateUserResponse:
    """Call the reactivate_user API operation."""
    return http.request_model(
        "DELETE",
        f"/v1/admin/users/{user_id}/suspension",
        ReactivateUserResponse,
    )


def suspend_user(
    http: HttpClient,
    *,
    user_id: str | UUID,
) -> SuspendUserResponse:
    """Call the suspend_user API operation."""
    return http.request_model(
        "PATCH",
        f"/v1/admin/users/{user_id}/suspension",
        SuspendUserResponse,
    )


def list_agents(
    http: HttpClient,
    *,
    filter_: str | None = None,
    orderBy: str | None = None,
    pageSize: int | None = None,
    pageToken: str | None = None,
) -> ListAgentsResponse:
    """Call the list_agents API operation."""
    params: dict[str, QueryValue] = {}
    if filter_ is not None:
        params["filter"] = filter_
    if orderBy is not None:
        params["orderBy"] = orderBy
    if pageSize is not None:
        params["pageSize"] = pageSize
    if pageToken is not None:
        params["pageToken"] = pageToken
    return http.request_model(
        "GET",
        "/v1/ard/agents",
        ListAgentsResponse,
        params=params,
    )


def explore(
    http: HttpClient,
    *,
    body: ExploreRequest,
) -> ExploreResponse:
    """Call the explore API operation."""
    return http.request_model(
        "POST",
        "/v1/ard/explore",
        ExploreResponse,
        json=body.model_dump(mode="json", exclude_none=True),
    )


def search(
    http: HttpClient,
    *,
    body: SearchRequest,
) -> SearchResponse:
    """Call the search API operation."""
    return http.request_model(
        "POST",
        "/v1/ard/search",
        SearchResponse,
        json=body.model_dump(mode="json", exclude_none=True),
    )


def record_source_snapshot(
    http: HttpClient,
    *,
    body: RecordSourceSnapshotRequest,
) -> RecordSourceSnapshotResponse:
    """Call the record_source_snapshot API operation."""
    return http.request_model(
        "POST",
        "/v1/ard/sources",
        RecordSourceSnapshotResponse,
        json=body.model_dump(mode="json", exclude_none=True),
    )


def get_source_status(
    http: HttpClient,
    *,
    source_type: str | None = None,
    limit: int | None = None,
) -> GetSourceStatusResponse:
    """Call the get_source_status API operation."""
    params: dict[str, QueryValue] = {}
    if source_type is not None:
        params["source_type"] = source_type
    if limit is not None:
        params["limit"] = limit
    return http.request_model(
        "GET",
        "/v1/ard/sources/status",
        GetSourceStatusResponse,
        params=params,
    )


def list_bounties(
    http: HttpClient,
    *,
    scope: str | None = None,
) -> list[ListBountiesResponse]:
    """Call the list_bounties API operation."""
    params: dict[str, QueryValue] = {}
    if scope is not None:
        params["scope"] = scope
    return [
        ListBountiesResponse.model_validate(item)
        for item in http.request_list(
            "GET",
            "/v1/bounties",
            params=params,
        )
    ]


def create_bounty(
    http: HttpClient,
    *,
    body: CreateBountyRequest,
) -> CreateBountyResponse:
    """Call the create_bounty API operation."""
    return http.request_model(
        "POST",
        "/v1/bounties",
        CreateBountyResponse,
        json=body.model_dump(mode="json", exclude_none=True),
    )


def cancel_bounty(
    http: HttpClient,
    *,
    bounty_id: str | UUID,
) -> CancelBountyResponse:
    """Call the cancel_bounty API operation."""
    return http.request_model(
        "DELETE",
        f"/v1/bounties/{bounty_id}",
        CancelBountyResponse,
    )


def get_bounty(
    http: HttpClient,
    *,
    bounty_id: str | UUID,
) -> GetBountyResponse:
    """Call the get_bounty API operation."""
    return http.request_model(
        "GET",
        f"/v1/bounties/{bounty_id}",
        GetBountyResponse,
    )


def update_bounty(
    http: HttpClient,
    *,
    bounty_id: str | UUID,
    body: UpdateBountyRequest,
) -> UpdateBountyResponse:
    """Call the update_bounty API operation."""
    return http.request_model(
        "PATCH",
        f"/v1/bounties/{bounty_id}",
        UpdateBountyResponse,
        json=body.model_dump(mode="json", exclude_none=True),
    )


def fund_bounty(
    http: HttpClient,
    *,
    bounty_id: str | UUID,
) -> FundBountyResponse:
    """Call the fund_bounty API operation."""
    return http.request_model(
        "PATCH",
        f"/v1/bounties/{bounty_id}/funding",
        FundBountyResponse,
    )


def create_bounty_payout(
    http: HttpClient,
    *,
    bounty_id: str | UUID,
) -> CreateBountyPayoutResponse:
    """Call the create_bounty_payout API operation."""
    return http.request_model(
        "POST",
        f"/v1/bounties/{bounty_id}/payouts",
        CreateBountyPayoutResponse,
    )


def open_bounty(
    http: HttpClient,
    *,
    bounty_id: str | UUID,
) -> OpenBountyResponse:
    """Call the open_bounty API operation."""
    return http.request_model(
        "PATCH",
        f"/v1/bounties/{bounty_id}/status",
        OpenBountyResponse,
    )


def list_bounty_submissions(
    http: HttpClient,
    *,
    bounty_id: str | UUID,
) -> list[ListBountySubmissionsResponse]:
    """Call the list_bounty_submissions API operation."""
    return [
        ListBountySubmissionsResponse.model_validate(item)
        for item in http.request_list(
            "GET",
            f"/v1/bounties/{bounty_id}/submissions",
        )
    ]


def create_bounty_submission(
    http: HttpClient,
    *,
    bounty_id: str | UUID,
    body: CreateBountySubmissionRequest,
) -> CreateBountySubmissionResponse:
    """Call the create_bounty_submission API operation."""
    return http.request_model(
        "POST",
        f"/v1/bounties/{bounty_id}/submissions",
        CreateBountySubmissionResponse,
        json=body.model_dump(mode="json", exclude_none=True),
    )


def withdraw_bounty_submission(
    http: HttpClient,
    *,
    bounty_id: str | UUID,
    submission_id: str | UUID,
) -> WithdrawBountySubmissionResponse:
    """Call the withdraw_bounty_submission API operation."""
    return http.request_model(
        "DELETE",
        f"/v1/bounties/{bounty_id}/submissions/{submission_id}",
        WithdrawBountySubmissionResponse,
    )


def get_bounty_submission(
    http: HttpClient,
    *,
    bounty_id: str | UUID,
    submission_id: str | UUID,
) -> GetBountySubmissionResponse:
    """Call the get_bounty_submission API operation."""
    return http.request_model(
        "GET",
        f"/v1/bounties/{bounty_id}/submissions/{submission_id}",
        GetBountySubmissionResponse,
    )


def accept_bounty_submission(
    http: HttpClient,
    *,
    bounty_id: str | UUID,
    submission_id: str | UUID,
) -> AcceptBountySubmissionResponse:
    """Call the accept_bounty_submission API operation."""
    return http.request_model(
        "PATCH",
        f"/v1/bounties/{bounty_id}/submissions/{submission_id}/acceptance",
        AcceptBountySubmissionResponse,
    )


def open_submission_pr(
    http: HttpClient,
    *,
    bounty_id: str | UUID,
    submission_id: str | UUID,
) -> OpenSubmissionPrResponse:
    """Call the open_submission_pr API operation."""
    return http.request_model(
        "POST",
        f"/v1/bounties/{bounty_id}/submissions/{submission_id}/open-pr",
        OpenSubmissionPrResponse,
    )


def reject_bounty_submission(
    http: HttpClient,
    *,
    bounty_id: str | UUID,
    submission_id: str | UUID,
) -> RejectBountySubmissionResponse:
    """Call the reject_bounty_submission API operation."""
    return http.request_model(
        "PATCH",
        f"/v1/bounties/{bounty_id}/submissions/{submission_id}/rejection",
        RejectBountySubmissionResponse,
    )


def get_api_capabilities(
    http: HttpClient,
) -> GetApiCapabilitiesResponse:
    """Call the get_api_capabilities API operation."""
    return http.request_model(
        "GET",
        "/v1/capabilities",
        GetApiCapabilitiesResponse,
    )


def list_human_review_queue(
    http: HttpClient,
    *,
    limit: int | None = None,
    cursor: str | None = None,
) -> ListHumanReviewQueueResponse:
    """Call the list_human_review_queue API operation."""
    params: dict[str, QueryValue] = {}
    if limit is not None:
        params["limit"] = limit
    if cursor is not None:
        params["cursor"] = cursor
    return http.request_model(
        "GET",
        "/v1/course-reviews",
        ListHumanReviewQueueResponse,
        params=params,
    )


def get_human_review_detail(
    http: HttpClient,
    *,
    review_id: str | UUID,
) -> GetHumanReviewDetailResponse:
    """Call the get_human_review_detail API operation."""
    return http.request_model(
        "GET",
        f"/v1/course-reviews/{review_id}",
        GetHumanReviewDetailResponse,
    )


def approve_human_review(
    http: HttpClient,
    *,
    review_id: str | UUID,
    body: ApproveHumanReviewRequest,
) -> ApproveHumanReviewResponse:
    """Call the approve_human_review API operation."""
    return http.request_model(
        "PATCH",
        f"/v1/course-reviews/{review_id}/approval",
        ApproveHumanReviewResponse,
        json=body.model_dump(mode="json", exclude_none=True),
    )


def get_review_bundle(
    http: HttpClient,
    *,
    review_id: str | UUID,
) -> GetReviewBundleResponse:
    """Call the get_review_bundle API operation."""
    return http.request_model(
        "GET",
        f"/v1/course-reviews/{review_id}/bundle",
        GetReviewBundleResponse,
    )


def reject_human_review(
    http: HttpClient,
    *,
    review_id: str | UUID,
    body: RejectHumanReviewRequest,
) -> RejectHumanReviewResponse:
    """Call the reject_human_review API operation."""
    return http.request_model(
        "PATCH",
        f"/v1/course-reviews/{review_id}/rejection",
        RejectHumanReviewResponse,
        json=body.model_dump(mode="json", exclude_none=True),
    )


def create_course(
    http: HttpClient,
    *,
    body: CreateCourseRequest,
) -> CreateCourseResponse:
    """Call the create_course API operation."""
    return http.request_model(
        "POST",
        "/v1/courses",
        CreateCourseResponse,
        json=body.model_dump(mode="json", exclude_none=True),
    )


def list_my_courses(
    http: HttpClient,
    *,
    status: str | None = None,
    visibility: str | None = None,
    limit: int | None = None,
    cursor: str | None = None,
) -> ListMyCoursesResponse:
    """Call the list_my_courses API operation."""
    params: dict[str, QueryValue] = {}
    if status is not None:
        params["status"] = status
    if visibility is not None:
        params["visibility"] = visibility
    if limit is not None:
        params["limit"] = limit
    if cursor is not None:
        params["cursor"] = cursor
    return http.request_model(
        "GET",
        "/v1/courses/mine",
        ListMyCoursesResponse,
        params=params,
    )


def get_course(
    http: HttpClient,
    *,
    course_id: str | UUID,
) -> GetCourseResponse:
    """Call the get_course API operation."""
    return http.request_model(
        "GET",
        f"/v1/courses/{course_id}",
        GetCourseResponse,
    )


def update_course(
    http: HttpClient,
    *,
    course_id: str | UUID,
    body: UpdateCourseRequest,
) -> UpdateCourseResponse:
    """Call the update_course API operation."""
    return http.request_model(
        "PATCH",
        f"/v1/courses/{course_id}",
        UpdateCourseResponse,
        json=body.model_dump(mode="json", exclude_unset=True),
    )


def get_my_course_review(
    http: HttpClient,
    *,
    course_id: str | UUID,
    version_id: str | UUID | None = None,
) -> GetMyCourseReviewResponse:
    """Call the get_my_course_review API operation."""
    params: dict[str, QueryValue] = {}
    if version_id is not None:
        params["version_id"] = version_id
    return http.request_model(
        "GET",
        f"/v1/courses/{course_id}/my-review",
        GetMyCourseReviewResponse,
        params=params,
    )


def request_publication(
    http: HttpClient,
    *,
    course_id: str | UUID,
) -> RequestPublicationResponse:
    """Call the request_publication API operation."""
    return http.request_model(
        "POST",
        f"/v1/courses/{course_id}/publication-reviews",
        RequestPublicationResponse,
    )


def get_review_status(
    http: HttpClient,
    *,
    course_id: str | UUID,
    include_pass: bool | None = None,
) -> GetReviewStatusResponse:
    """Call the get_review_status API operation."""
    params: dict[str, QueryValue] = {}
    if include_pass is not None:
        params["include_pass"] = include_pass
    return http.request_model(
        "GET",
        f"/v1/courses/{course_id}/publication-reviews/latest",
        GetReviewStatusResponse,
        params=params,
    )


def purchase_course(
    http: HttpClient,
    *,
    course_id: str | UUID,
    body: PurchaseCourseRequest,
) -> PurchaseCourseResponse:
    """Call the purchase_course API operation."""
    return http.request_model(
        "POST",
        f"/v1/courses/{course_id}/purchase",
        PurchaseCourseResponse,
        json=body.model_dump(mode="json", exclude_none=True),
    )


def get_course_review_feedback(
    http: HttpClient,
    *,
    course_id: str | UUID,
) -> GetCourseReviewFeedbackResponse:
    """Call the get_course_review_feedback API operation."""
    return http.request_model(
        "GET",
        f"/v1/courses/{course_id}/review-feedback",
        GetCourseReviewFeedbackResponse,
    )


def list_course_reviews(
    http: HttpClient,
    *,
    course_id: str | UUID,
    version: str | None = None,
    limit: int | None = None,
    cursor: str | None = None,
) -> ListCourseReviewsResponse:
    """Call the list_course_reviews API operation."""
    params: dict[str, QueryValue] = {}
    if version is not None:
        params["version"] = version
    if limit is not None:
        params["limit"] = limit
    if cursor is not None:
        params["cursor"] = cursor
    return http.request_model(
        "GET",
        f"/v1/courses/{course_id}/reviews",
        ListCourseReviewsResponse,
        params=params,
    )


def delete_course_source_link(
    http: HttpClient,
    *,
    course_id: str | UUID,
) -> JsonObject:
    """Call the delete_course_source_link API operation."""
    return cast(
        JsonObject,
        http.request(
            "DELETE",
            f"/v1/courses/{course_id}/source-link",
        ),
    )


def get_course_source_link(
    http: HttpClient,
    *,
    course_id: str | UUID,
) -> GetCourseSourceLinkResponse:
    """Call the get_course_source_link API operation."""
    return http.request_model(
        "GET",
        f"/v1/courses/{course_id}/source-link",
        GetCourseSourceLinkResponse,
    )


def set_course_source_link(
    http: HttpClient,
    *,
    course_id: str | UUID,
    body: SetCourseSourceLinkRequest,
) -> SetCourseSourceLinkResponse:
    """Call the set_course_source_link API operation."""
    return http.request_model(
        "PUT",
        f"/v1/courses/{course_id}/source-link",
        SetCourseSourceLinkResponse,
        json=body.model_dump(mode="json", exclude_none=True),
    )


def create_upload_session(
    http: HttpClient,
    *,
    course_id: str | UUID,
    body: CreateCourseVersionUploadSessionRequest,
) -> CreateCourseVersionUploadSessionResponse:
    """Call the create_upload_session API operation."""
    return http.request_model(
        "POST",
        f"/v1/courses/{course_id}/versions",
        CreateCourseVersionUploadSessionResponse,
        json=body.model_dump(mode="json", exclude_none=True),
    )


def get_course_version(
    http: HttpClient,
    *,
    course_id: str | UUID,
    version_id: str | UUID,
) -> GetCourseVersionResponse:
    """Call the get_course_version API operation."""
    return http.request_model(
        "GET",
        f"/v1/courses/{course_id}/versions/{version_id}",
        GetCourseVersionResponse,
    )


def upsert_course_review(
    http: HttpClient,
    *,
    course_id: str | UUID,
    version_id: str | UUID,
    body: UpsertCourseReviewRequest,
) -> UpsertCourseReviewResponse:
    """Call the upsert_course_review API operation."""
    return http.request_model(
        "PUT",
        f"/v1/courses/{course_id}/versions/{version_id}/review",
        UpsertCourseReviewResponse,
        json=body.model_dump(mode="json", exclude_none=True),
    )


def complete_upload_session(
    http: HttpClient,
    *,
    course_id: str | UUID,
    version_id: str | UUID,
) -> CompleteCourseVersionUploadSessionResponse:
    """Call the complete_upload_session API operation."""
    return http.request_model(
        "PATCH",
        f"/v1/courses/{course_id}/versions/{version_id}/upload-session",
        CompleteCourseVersionUploadSessionResponse,
    )


def get_credit_balance(
    http: HttpClient,
) -> GetCreditBalanceResponse:
    """Call the get_credit_balance API operation."""
    return http.request_model(
        "GET",
        "/v1/credits/balance",
        GetCreditBalanceResponse,
    )


def list_credit_ledger(
    http: HttpClient,
) -> list[ListCreditLedgerResponse]:
    """Call the list_credit_ledger API operation."""
    return [
        ListCreditLedgerResponse.model_validate(item)
        for item in http.request_list(
            "GET",
            "/v1/credits/ledger",
        )
    ]


def create_credit_top_up(
    http: HttpClient,
    *,
    body: CreateCreditTopUpRequest,
) -> CreateCreditTopUpResponse:
    """Call the create_credit_top_up API operation."""
    return http.request_model(
        "POST",
        "/v1/credits/top-ups",
        CreateCreditTopUpResponse,
        json=body.model_dump(mode="json", exclude_none=True),
    )


def get_credit_top_up(
    http: HttpClient,
    *,
    top_up_id: str | UUID,
) -> GetCreditTopUpResponse:
    """Call the get_credit_top_up API operation."""
    return http.request_model(
        "GET",
        f"/v1/credits/top-ups/{top_up_id}",
        GetCreditTopUpResponse,
    )


def upload_eval_contract(
    http: HttpClient,
    *,
    body: UploadEvalContractRequest,
) -> JsonObject:
    """Call the upload_eval_contract API operation."""
    return cast(
        JsonObject,
        http.request(
            "POST",
            "/v1/evals/contracts",
            json=body.model_dump(mode="json", exclude_none=True),
        ),
    )


def get_eval_contract(
    http: HttpClient,
    *,
    ref: str,
) -> dict[str, JsonValue]:
    """Call the get_eval_contract API operation."""
    return cast(
        dict[str, JsonValue],
        http.request(
            "GET",
            f"/v1/evals/contracts/{ref}",
        ),
    )


def submit_eval_result(
    http: HttpClient,
    *,
    body: SubmitEvalResultRequest,
) -> JsonObject:
    """Call the submit_eval_result API operation."""
    return cast(
        JsonObject,
        http.request(
            "POST",
            "/v1/evals/results",
            json=body.model_dump(mode="json", exclude_none=True),
        ),
    )


def list_execution_jobs(
    http: HttpClient,
    *,
    status: str | None = None,
    job_type: str | None = None,
    limit: int | None = None,
    offset: int | None = None,
) -> ListExecutionJobsResponse:
    """Call the list_execution_jobs API operation."""
    params: dict[str, QueryValue] = {}
    if status is not None:
        params["status"] = status
    if job_type is not None:
        params["job_type"] = job_type
    if limit is not None:
        params["limit"] = limit
    if offset is not None:
        params["offset"] = offset
    return http.request_model(
        "GET",
        "/v1/executions/jobs",
        ListExecutionJobsResponse,
        params=params,
    )


def create_execution_job(
    http: HttpClient,
    *,
    body: CreateExecutionJobRequest,
) -> CreateExecutionJobResponse:
    """Call the create_execution_job API operation."""
    return http.request_model(
        "POST",
        "/v1/executions/jobs",
        CreateExecutionJobResponse,
        json=body.model_dump(mode="json", exclude_none=True),
    )


def get_execution_job(
    http: HttpClient,
    *,
    job_id: str | UUID,
) -> GetExecutionJobResponse:
    """Call the get_execution_job API operation."""
    return http.request_model(
        "GET",
        f"/v1/executions/jobs/{job_id}",
        GetExecutionJobResponse,
    )


def cancel_execution_job(
    http: HttpClient,
    *,
    job_id: str | UUID,
) -> CancelExecutionJobResponse:
    """Call the cancel_execution_job API operation."""
    return http.request_model(
        "POST",
        f"/v1/executions/jobs/{job_id}/cancel",
        CancelExecutionJobResponse,
    )


def list_my_feedback(
    http: HttpClient,
    *,
    limit: int | None = None,
    offset: int | None = None,
) -> ListMyFeedbackResponse:
    """Call the list_my_feedback API operation."""
    params: dict[str, QueryValue] = {}
    if limit is not None:
        params["limit"] = limit
    if offset is not None:
        params["offset"] = offset
    return http.request_model(
        "GET",
        "/v1/feedback/mine",
        ListMyFeedbackResponse,
        params=params,
    )


def revoke_github_identity(
    http: HttpClient,
) -> JsonObject:
    """Call the revoke_github_identity API operation."""
    return cast(
        JsonObject,
        http.request(
            "DELETE",
            "/v1/identity/github",
        ),
    )


def get_github_identity(
    http: HttpClient,
) -> GithubIdentityResponse:
    """Call the get_github_identity API operation."""
    return http.request_model(
        "GET",
        "/v1/identity/github",
        GithubIdentityResponse,
    )


def begin_github_authorization(
    http: HttpClient,
    *,
    body: AuthorizeRequest,
) -> AuthorizeResponse:
    """Call the begin_github_authorization API operation."""
    return http.request_model(
        "POST",
        "/v1/identity/github/authorize",
        AuthorizeResponse,
        json=body.model_dump(mode="json", exclude_none=True),
    )


def complete_github_callback(
    http: HttpClient,
    *,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
) -> JsonObject:
    """Call the complete_github_callback API operation."""
    params: dict[str, QueryValue] = {}
    if code is not None:
        params["code"] = code
    if state is not None:
        params["state"] = state
    if error is not None:
        params["error"] = error
    return cast(
        JsonObject,
        http.request(
            "GET",
            "/v1/identity/github/callback",
            params=params,
        ),
    )


def begin_github_device_flow(
    http: HttpClient,
    *,
    body: DeviceBeginRequest,
) -> DeviceBeginResponse:
    """Call the begin_github_device_flow API operation."""
    return http.request_model(
        "POST",
        "/v1/identity/github/device",
        DeviceBeginResponse,
        json=body.model_dump(mode="json", exclude_none=True),
    )


def poll_github_device_flow(
    http: HttpClient,
    *,
    body: DevicePollRequest,
) -> DevicePollGrantedResponse:
    """Call the poll_github_device_flow API operation."""
    return http.request_model(
        "POST",
        "/v1/identity/github/device/poll",
        DevicePollGrantedResponse,
        json=body.model_dump(mode="json", exclude_none=True),
    )


def create_user_with_agent(
    http: HttpClient,
    *,
    body: CreateUserWithAgentRequest,
) -> CreateUserWithAgentResponse:
    """Call the create_user_with_agent API operation."""
    return http.request_model(
        "POST",
        "/v1/identity/users",
        CreateUserWithAgentResponse,
        json=body.model_dump(mode="json", exclude_none=True),
    )


def add_agent_to_user(
    http: HttpClient,
    *,
    user_id: str | UUID,
    body: AddAgentToUserRequest,
) -> AddAgentToUserResponse:
    """Call the add_agent_to_user API operation."""
    return http.request_model(
        "POST",
        f"/v1/identity/users/{user_id}/agents",
        AddAgentToUserResponse,
        json=body.model_dump(mode="json", exclude_none=True),
    )


def rotate_agent_api_key(
    http: HttpClient,
    *,
    user_id: str | UUID,
    agent_id: str | UUID,
    body: RotateAgentApiKeyRequest,
) -> RotateAgentApiKeyResponse:
    """Call the rotate_agent_api_key API operation."""
    return http.request_model(
        "POST",
        f"/v1/identity/users/{user_id}/agents/{agent_id}/api-keys",
        RotateAgentApiKeyResponse,
        json=body.model_dump(mode="json", exclude_none=True),
    )


def get_indexed_listing(
    http: HttpClient,
    *,
    listing_id: str | UUID,
) -> GetIndexedListingResponse:
    """Call the get_indexed_listing API operation."""
    return http.request_model(
        "GET",
        f"/v1/indexed-listings/{listing_id}",
        GetIndexedListingResponse,
    )


def search_listings(
    http: HttpClient,
    *,
    query: str | None = None,
    tags: str | None = None,
    category: str | None = None,
    language: str | None = None,
    price_min: int | None = None,
    price_max: int | None = None,
    sort: str | None = None,
    limit: int | None = None,
    cursor: str | None = None,
    include_indexed: bool | None = None,
    tier: str | None = None,
) -> SearchListingsResponse:
    """Call the search_listings API operation."""
    params: dict[str, QueryValue] = {}
    if query is not None:
        params["query"] = query
    if tags is not None:
        params["tags"] = tags
    if category is not None:
        params["category"] = category
    if language is not None:
        params["language"] = language
    if price_min is not None:
        params["price_min"] = price_min
    if price_max is not None:
        params["price_max"] = price_max
    if sort is not None:
        params["sort"] = sort
    if limit is not None:
        params["limit"] = limit
    if cursor is not None:
        params["cursor"] = cursor
    if include_indexed is not None:
        params["include_indexed"] = include_indexed
    if tier is not None:
        params["tier"] = tier
    return http.request_model(
        "GET",
        "/v1/listings",
        SearchListingsResponse,
        params=params,
    )


def list_notifications(
    http: HttpClient,
    *,
    unread_only: bool | None = None,
    type_: str | None = None,
    limit: int | None = None,
    cursor: str | None = None,
) -> ListNotificationsResponse:
    """Call the list_notifications API operation."""
    params: dict[str, QueryValue] = {}
    if unread_only is not None:
        params["unread_only"] = unread_only
    if type_ is not None:
        params["type"] = type_
    if limit is not None:
        params["limit"] = limit
    if cursor is not None:
        params["cursor"] = cursor
    return http.request_model(
        "GET",
        "/v1/notifications",
        ListNotificationsResponse,
        params=params,
    )


def get_unread_count(
    http: HttpClient,
) -> GetUnreadCountResponse:
    """Call the get_unread_count API operation."""
    return http.request_model(
        "GET",
        "/v1/notifications/unread-count",
        GetUnreadCountResponse,
    )


def request_cash_out(
    http: HttpClient,
    *,
    body: RequestCashOutRequest,
) -> RequestCashOutResponse:
    """Call the request_cash_out API operation."""
    return http.request_model(
        "POST",
        "/v1/payments/cash-out",
        RequestCashOutResponse,
        json=body.model_dump(mode="json", exclude_none=True),
    )


def create_onboarding_link(
    http: HttpClient,
) -> OnboardingLinkResponse:
    """Call the create_onboarding_link API operation."""
    return http.request_model(
        "POST",
        "/v1/payments/connect-onboarding-sessions",
        OnboardingLinkResponse,
    )


def get_creator_earnings(
    http: HttpClient,
) -> GetCreatorEarningsResponse:
    """Call the get_creator_earnings API operation."""
    return http.request_model(
        "GET",
        "/v1/payments/creator-earnings",
        GetCreatorEarningsResponse,
    )


def get_order(
    http: HttpClient,
    *,
    order_id: str | UUID,
) -> OrderResponse:
    """Call the get_order API operation."""
    return http.request_model(
        "GET",
        f"/v1/payments/orders/{order_id}",
        OrderResponse,
    )


def get_seller_readiness(
    http: HttpClient,
) -> SellerReadinessResponse:
    """Call the get_seller_readiness API operation."""
    return http.request_model(
        "GET",
        "/v1/payments/seller-readiness",
        SellerReadinessResponse,
    )


def list_referral_attributions(
    http: HttpClient,
) -> list[ListReferralAttributionsResponse]:
    """Call the list_referral_attributions API operation."""
    return [
        ListReferralAttributionsResponse.model_validate(item)
        for item in http.request_list(
            "GET",
            "/v1/referrals/attributions",
        )
    ]


def get_referral_code(
    http: HttpClient,
) -> GetReferralCodeResponse:
    """Call the get_referral_code API operation."""
    return http.request_model(
        "GET",
        "/v1/referrals/code",
        GetReferralCodeResponse,
    )


def get_referral_link(
    http: HttpClient,
    *,
    course_id: str | UUID | None = None,
) -> GetReferralLinkResponse:
    """Call the get_referral_link API operation."""
    params: dict[str, QueryValue] = {}
    if course_id is not None:
        params["course_id"] = course_id
    return http.request_model(
        "GET",
        "/v1/referrals/link",
        GetReferralLinkResponse,
        params=params,
    )


def get_referral_stats(
    http: HttpClient,
) -> GetReferralStatsResponse:
    """Call the get_referral_stats API operation."""
    return http.request_model(
        "GET",
        "/v1/referrals/stats",
        GetReferralStatsResponse,
    )


def create_report(
    http: HttpClient,
    *,
    body: CreateReportRequest,
) -> CreateReportResponse:
    """Call the create_report API operation."""
    return http.request_model(
        "POST",
        "/v1/reports",
        CreateReportResponse,
        json=body.model_dump(mode="json", exclude_none=True),
    )


def list_resources(
    http: HttpClient,
    *,
    resource_type: str | None = None,
    lifecycle_status: str | None = None,
    cursor: str | None = None,
    limit: int | None = None,
) -> ListResourcesResponse:
    """Call the list_resources API operation."""
    params: dict[str, QueryValue] = {}
    if resource_type is not None:
        params["resource_type"] = resource_type
    if lifecycle_status is not None:
        params["lifecycle_status"] = lifecycle_status
    if cursor is not None:
        params["cursor"] = cursor
    if limit is not None:
        params["limit"] = limit
    return http.request_model(
        "GET",
        "/v1/resources",
        ListResourcesResponse,
        params=params,
    )


def get_resource(
    http: HttpClient,
    *,
    resource_id: str | UUID,
) -> GetResourceResponse:
    """Call the get_resource API operation."""
    return http.request_model(
        "GET",
        f"/v1/resources/{resource_id}",
        GetResourceResponse,
    )


def list_resource_feedback(
    http: HttpClient,
    *,
    resource_id: str | UUID,
    limit: int | None = None,
    offset: int | None = None,
) -> ListResourceFeedbackResponse:
    """Call the list_resource_feedback API operation."""
    params: dict[str, QueryValue] = {}
    if limit is not None:
        params["limit"] = limit
    if offset is not None:
        params["offset"] = offset
    return http.request_model(
        "GET",
        f"/v1/resources/{resource_id}/feedback",
        ListResourceFeedbackResponse,
        params=params,
    )


def get_feedback_summary(
    http: HttpClient,
    *,
    resource_id: str | UUID,
) -> GetFeedbackSummaryResponse:
    """Call the get_feedback_summary API operation."""
    return http.request_model(
        "GET",
        f"/v1/resources/{resource_id}/feedback/summary",
        GetFeedbackSummaryResponse,
    )


def list_resource_versions(
    http: HttpClient,
    *,
    resource_id: str | UUID,
    limit: int | None = None,
) -> ListResourceVersionsResponse:
    """Call the list_resource_versions API operation."""
    params: dict[str, QueryValue] = {}
    if limit is not None:
        params["limit"] = limit
    return http.request_model(
        "GET",
        f"/v1/resources/{resource_id}/versions",
        ListResourceVersionsResponse,
        params=params,
    )


def get_acquisition_plan(
    http: HttpClient,
    *,
    resource_id: str | UUID,
    version_id: str | UUID,
    channel: str | None = None,
) -> GetAcquisitionPlanResponse:
    """Call the get_acquisition_plan API operation."""
    params: dict[str, QueryValue] = {}
    if channel is not None:
        params["channel"] = channel
    return http.request_model(
        "GET",
        f"/v1/resources/{resource_id}/versions/{version_id}/acquisition-plan",
        GetAcquisitionPlanResponse,
        params=params,
    )


def create_artifact_download(
    http: HttpClient,
    *,
    resource_id: str | UUID,
    version_id: str | UUID,
) -> CreateArtifactDownloadResponse:
    """Call the create_artifact_download API operation."""
    return http.request_model(
        "POST",
        f"/v1/resources/{resource_id}/versions/{version_id}/download",
        CreateArtifactDownloadResponse,
    )


def submit_feedback(
    http: HttpClient,
    *,
    resource_id: str | UUID,
    version_id: str | UUID,
    body: SubmitFeedbackRequest,
) -> SubmitFeedbackResponse:
    """Call the submit_feedback API operation."""
    return http.request_model(
        "POST",
        f"/v1/resources/{resource_id}/versions/{version_id}/feedback",
        SubmitFeedbackResponse,
        json=body.model_dump(mode="json", exclude_none=True),
    )


def submit_usage_receipt(
    http: HttpClient,
    *,
    resource_id: str | UUID,
    version_id: str | UUID,
    body: SubmitUsageReceiptRequest,
) -> SubmitUsageReceiptResponse:
    """Call the submit_usage_receipt API operation."""
    return http.request_model(
        "POST",
        f"/v1/resources/{resource_id}/versions/{version_id}/usage-receipts",
        SubmitUsageReceiptResponse,
        json=body.model_dump(mode="json", exclude_none=True),
    )


def ingest_catalog_entries(
    http: HttpClient,
    *,
    body: IngestCatalogEntriesRequest,
) -> IngestCatalogEntriesResponse:
    """Call the ingest_catalog_entries API operation."""
    return http.request_model(
        "POST",
        "/v1/resources:ingest-catalog",
        IngestCatalogEntriesResponse,
        json=body.model_dump(mode="json", exclude_none=True),
    )


def list_runners(
    http: HttpClient,
) -> ListRunnersResponse:
    """Call the list_runners API operation."""
    return http.request_model(
        "GET",
        "/v1/runners",
        ListRunnersResponse,
    )


def enroll_runner(
    http: HttpClient,
    *,
    body: EnrollRunnerRequest,
) -> EnrollRunnerResponse:
    """Call the enroll_runner API operation."""
    return http.request_model(
        "POST",
        "/v1/runners/enroll",
        EnrollRunnerResponse,
        json=body.model_dump(mode="json", exclude_none=True),
    )


def runner_heartbeat(
    http: HttpClient,
    *,
    body: RunnerHeartbeatRequest,
) -> RunnerHeartbeatResponse:
    """Call the runner_heartbeat API operation."""
    return http.request_model(
        "POST",
        "/v1/runners/heartbeat",
        RunnerHeartbeatResponse,
        json=body.model_dump(mode="json", exclude_none=True),
    )


def upload_execution_artifact(
    http: HttpClient,
    *,
    job_id: str,
    name: str,
) -> UploadExecutionArtifactResponse:
    """Call the upload_execution_artifact API operation."""
    return http.request_model(
        "POST",
        f"/v1/runners/jobs/{job_id}/artifacts/{name}",
        UploadExecutionArtifactResponse,
    )


def submit_execution_receipt(
    http: HttpClient,
    *,
    job_id: str,
    body: SubmitExecutionReceiptRequest,
) -> SubmitExecutionReceiptResponse:
    """Call the submit_execution_receipt API operation."""
    return http.request_model(
        "POST",
        f"/v1/runners/jobs/{job_id}/receipt",
        SubmitExecutionReceiptResponse,
        json=body.model_dump(mode="json", exclude_none=True),
    )


def lease_execution_job(
    http: HttpClient,
    *,
    body: LeaseExecutionJobRequest,
) -> LeaseExecutionJobResponse:
    """Call the lease_execution_job API operation."""
    return http.request_model(
        "POST",
        "/v1/runners/lease",
        LeaseExecutionJobResponse,
        json=body.model_dump(mode="json", exclude_none=True),
    )


def rotate_runner_key(
    http: HttpClient,
) -> RotateRunnerKeyResponse:
    """Call the rotate_runner_key API operation."""
    return http.request_model(
        "POST",
        "/v1/runners/rotate-key",
        RotateRunnerKeyResponse,
    )


def redeem_setup_token(
    http: HttpClient,
    *,
    body: RedeemSetupTokenRequest,
) -> RedeemSetupTokenResponse:
    """Call the redeem_setup_token API operation."""
    return http.request_model(
        "POST",
        "/v1/setup-tokens/redeem",
        RedeemSetupTokenResponse,
        json=body.model_dump(mode="json", exclude_none=True),
    )


def get_setup_token_status(
    http: HttpClient,
    *,
    prefix: str,
) -> dict[str, str]:
    """Call the get_setup_token_status API operation."""
    return cast(
        dict[str, str],
        http.request(
            "GET",
            f"/v1/setup-tokens/{prefix}",
        ),
    )


def setup_github_callback(
    http: HttpClient,
    *,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
) -> JsonObject:
    """Call the setup_github_callback API operation."""
    params: dict[str, QueryValue] = {}
    if code is not None:
        params["code"] = code
    if state is not None:
        params["state"] = state
    if error is not None:
        params["error"] = error
    return cast(
        JsonObject,
        http.request(
            "GET",
            "/v1/setup/github/callback",
            params=params,
        ),
    )


def setup_github_start(
    http: HttpClient,
) -> JsonObject:
    """Call the setup_github_start API operation."""
    return cast(
        JsonObject,
        http.request(
            "GET",
            "/v1/setup/github/start",
        ),
    )


def claim_setup_handoff(
    http: HttpClient,
    *,
    body: ClaimSetupHandoffRequest,
) -> ClaimSetupHandoffResponse:
    """Call the claim_setup_handoff API operation."""
    return http.request_model(
        "POST",
        "/v1/setup/handoff/claim",
        ClaimSetupHandoffResponse,
        json=body.model_dump(mode="json", exclude_none=True),
    )

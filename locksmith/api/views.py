from rest_framework import viewsets, permissions
from .permissions import IsAdmin
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework.decorators import action
from .models import Service, AdminSettings
from .serializers import AdminSettingsSerializer, CustomerServiceRequestSerializer ,LocksmithCreateSerializer
from .models import User, Locksmith, CarKeyDetails, Service, Transaction, ServiceRequest, ServiceBid ,CustomerServiceRequest , Customer , AdminService,LocksmithServices , Booking
from .serializers import UserSerializer, LocksmithSerializer, CarKeyDetailsSerializer, ServiceSerializer, TransactionSerializer, ServiceRequestSerializer, ServiceBidSerializer,LocksmithServiceSerializer
from .serializers import UserCreateSerializer , CustomerSerializer , AdminServiceSerializer , BookingSerializer
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.permissions import AllowAny
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework import status
from django.contrib.auth import authenticate
import pyotp

from rest_framework import viewsets, permissions, status
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.contrib.gis.geos import Point
from django.contrib.gis.db.models.functions import Distance
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync



class CreateAdminUserView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]  # Only authenticated admin users can create other users

    def post(self, request):
        # Validate and create a new admin user
        serializer = UserCreateSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save(is_staff=True)  # Set user as admin (staff)
            return Response({"message": "user created successfully", "user": serializer.data})
        return Response(serializer.errors, status=400)
    
    
# User Registration API
class UserRegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = UserCreateSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            refresh = RefreshToken.for_user(user)

            totp_details = serializer.get_totp_details(user)  # Pass user instance

            return Response({
                'message': 'User registered successfully',
                'user': {
                    'id': user.id,
                    'username': user.username,
                    'email': user.email,
                    'role': user.role,
                    'totp_enabled': user.totp_enabled,
                    'totp_secret': totp_details["totp_secret"],  # TOTP Key in Response
                    'totp_qr_code': totp_details["totp_qr_code"],  # Base64 QR Code
                    'totp_qr_code_url': totp_details["qr_code_url"],  # QR Image URL
                },
                'access': str(refresh.access_token),
                'refresh': str(refresh)
            }, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

# class LocksmithRegisterView(APIView):
#     permission_classes = [AllowAny]

#     def post(self, request):
#         serializer = UserCreateSerializer(data=request.data)
#         if serializer.is_valid():
#             user = serializer.save()
#             user.set_password(request.data['password'])  # Hash password
#             user.save()

#             # Create Locksmith Profile
#             locksmith = Locksmith.objects.create(
#                 user=user,
#                 is_approved=False,
#                 address=request.data.get('address', ''),  
#                 contact_number=request.data.get('contact_number', ''),  
#                 pcc_file=request.data.get('pcc_file', None),  
#                 license_file=request.data.get('license_file', None),  
#                 photo=request.data.get('photo', None),  
#             )

#             refresh = RefreshToken.for_user(user)
#             return Response({
#                 'message': 'Locksmith registered successfully, pending approval',
#                 'user': serializer.data,
#                 # 'role':serializer.data,
#                 'access': str(refresh.access_token),
#                 'refresh': str(refresh)
#             }, status=status.HTTP_201_CREATED)

#         return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
class LocksmithRegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LocksmithCreateSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            user.set_password(request.data['password'])  # Hash password
            user.role = 'locksmith'  # Explicitly set the role
            user.save()

            # Generate authentication tokens
            refresh = RefreshToken.for_user(user)

            # Generate TOTP details for Locksmith
            totp_details = serializer.get_totp_details(user)

            return Response({
                'message': 'Locksmith registered successfully. Please complete your profile.',
                'user': {
                    'id': user.id,
                    'username': user.username,
                    'email': user.email,
                    'role': user.role,
                    'totp_enabled': user.totp_enabled,
                    'totp_secret': totp_details["totp_secret"],  # TOTP Key in Response
                    'totp_qr_code': totp_details["totp_qr_code"],  # Base64 QR Code
                    'totp_qr_code_url': totp_details["qr_code_url"],  # QR Image URL
                },
                'access': str(refresh.access_token),
                'refresh': str(refresh)
            }, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            refresh_token = request.data["refresh"]
            token = RefreshToken(refresh_token)
            token.blacklist()  # Blacklist the refresh token

            return Response({"message": "Logout successful"}, status=status.HTTP_205_RESET_CONTENT)

        except Exception as e:
            return Response({"error": "Invalid token"}, status=status.HTTP_400_BAD_REQUEST)    
    
    
class IsLocksmith(permissions.BasePermission):
    """
    Custom permission to allow only locksmiths to access the view.
    """

    def has_permission(self, request, view):
        # Ensure the user is authenticated and has the locksmith role
        return request.user and request.user.is_authenticated and request.user.role == "locksmith"
    
    
    
class LocksmithProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        """
        Create a new locksmith profile for the logged-in user.
        """
        user = request.user

        # Ensure the user is a locksmith
        if user.role != 'locksmith':
            return Response({"error": "Unauthorized. Only locksmiths can create profiles."}, status=status.HTTP_403_FORBIDDEN)

        # Check if the locksmith profile already exists
        if hasattr(user, 'locksmith'):
            return Response({"error": "Profile already exists."}, status=status.HTTP_400_BAD_REQUEST)

        # Create a new locksmith profile
        serializer = LocksmithSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(user=user)
            return Response({"message": "Profile created successfully", "data": serializer.data}, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def put(self, request):
        """
        Update an existing locksmith profile.
        """
        user = request.user

        # Ensure the locksmith profile exists
        try:
            locksmith = user.locksmith
        except Locksmith.DoesNotExist:
            return Response({"error": "Locksmith profile not found."}, status=status.HTTP_404_NOT_FOUND)

        serializer = LocksmithSerializer(locksmith, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response({"message": "Profile updated successfully", "data": serializer.data}, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    
class Approvalverification(viewsets.ModelViewSet):
    serializer_class = LocksmithSerializer
    permission_classes = [IsAuthenticated]  # Ensures only authenticated users can access

    def get_queryset(self):
        """
        Filter locksmith profiles by logged-in user.
        """
        user = self.request.user
        return Locksmith.objects.filter(user=user)  # Return only the locksmith profile of the logged-in user

    def retrieve(self, request, *args, **kwargs):
        """
        Retrieve a specific locksmith profile by ID.
        """
        user = self.request.user
        locksmith_id = self.kwargs.get("pk")  # Get locksmith ID from the URL
        
        try:
            locksmith = Locksmith.objects.get(id=locksmith_id, user=user)
            serializer = self.get_serializer(locksmith)
            return Response(serializer.data)
        except Locksmith.DoesNotExist:
            return Response({"error": "Locksmith profile not found."}, status=404)
    
       
# class LocksmithViewSet(viewsets.ModelViewSet):
#     queryset = Locksmith.objects.all()
#     serializer_class = LocksmithSerializer
#     permission_classes = [IsAdmin]  # Only Admin can manage locksmiths

#     @action(detail=True, methods=['put'], permission_classes=[IsAdmin])
#     def verify_locksmith(self, request, pk=None):
#         locksmith = self.get_object()
#         locksmith.is_verified = True
#         locksmith.is_approved = True  # Approve upon verification
#         locksmith.save()
#         locksmith_data = {
#             "id": locksmith.id,
#             "user": {
#                 "id": locksmith.user.id,
#                 "username": locksmith.user.username,
#                 "full_name": locksmith.user.get_full_name(),
#                 "email": locksmith.user.email
#             },
#             "service_area": locksmith.service_area,
#             "address": locksmith.address,
#             "contact_number": locksmith.contact_number,
#             "latitude": locksmith.latitude,
#             "longitude": locksmith.longitude,
#             "reputation_score": str(locksmith.reputation_score),  # Convert Decimal to string for JSON
#             "pcc_file": locksmith.pcc_file.url if locksmith.pcc_file else None,
#             "license_file": locksmith.license_file.url if locksmith.license_file else None,
#             "photo": locksmith.photo.url if locksmith.photo else None,
#             "is_verified": locksmith.is_verified,
#             "is_approved": locksmith.is_approved,
#             "created_at": locksmith.created_at.strftime('%Y-%m-%d %H:%M:%S') if hasattr(locksmith, 'created_at') else None,
#             "updated_at": locksmith.updated_at.strftime('%Y-%m-%d %H:%M:%S') if hasattr(locksmith, 'updated_at') else None
#         }

#         return Response({
#             'status': 'Locksmith details verified and approved',
#             'locksmith_data': locksmith_data
#         })

#     @action(detail=True, methods=['put'], permission_classes=[IsAdmin])
#     def reject_locksmith(self, request, pk=None):
#         locksmith = self.get_object()
#         locksmith.is_verified = False
#         locksmith.is_approved = False
#         locksmith.save()
#         locksmith_data = {
#             "id": locksmith.id,
#             "user": {
#                 "id": locksmith.user.id,
#                 "username": locksmith.user.username,
#                 "full_name": locksmith.user.get_full_name(),
#                 "email": locksmith.user.email
#             },
#             "service_area": locksmith.service_area,
#             "address": locksmith.address,
#             "contact_number": locksmith.contact_number,
#             "latitude": locksmith.latitude,
#             "longitude": locksmith.longitude,
#             "reputation_score": str(locksmith.reputation_score),  # Convert Decimal to string for JSON
#             "pcc_file": locksmith.pcc_file.url if locksmith.pcc_file else None,
#             "license_file": locksmith.license_file.url if locksmith.license_file else None,
#             "photo": locksmith.photo.url if locksmith.photo else None,
#             "is_verified": locksmith.is_verified,
#             "is_approved": locksmith.is_approved,
#             "created_at": locksmith.created_at.strftime('%Y-%m-%d %H:%M:%S') if hasattr(locksmith, 'created_at') else None,
#             "updated_at": locksmith.updated_at.strftime('%Y-%m-%d %H:%M:%S') if hasattr(locksmith, 'updated_at') else None
#         }

#         return Response({
#             'status': 'locksmith details rejected',
#             'locksmith_data': locksmith_data
#         })


#     @action(detail=True, methods=['get'], permission_classes=[IsAdmin])
#     def verify_locksmith_details(self, request, pk=None):
#         locksmith = self.get_object()

#         locksmith_data = {
#             "id": locksmith.id,
#             "user": {
#                 "id": locksmith.user.id,
#                 "username": locksmith.user.username,
#                 "full_name": locksmith.user.get_full_name(),
#                 "email": locksmith.user.email
#             },
#             "service_area": locksmith.service_area,
#             "address": locksmith.address,
#             "contact_number": locksmith.contact_number,
#             "latitude": locksmith.latitude,
#             "longitude": locksmith.longitude,
#             "reputation_score": str(locksmith.reputation_score),  # Convert Decimal to string for JSON
#             "pcc_file": locksmith.pcc_file.url if locksmith.pcc_file else None,
#             "license_file": locksmith.license_file.url if locksmith.license_file else None,
#             "photo": locksmith.photo.url if locksmith.photo else None,
#             "is_verified": locksmith.is_verified,
#             "is_approved": locksmith.is_approved,
#             "created_at": locksmith.created_at.strftime('%Y-%m-%d %H:%M:%S') if hasattr(locksmith, 'created_at') else None,
#             "updated_at": locksmith.updated_at.strftime('%Y-%m-%d %H:%M:%S') if hasattr(locksmith, 'updated_at') else None
#         }

#         return Response(locksmith_data)



class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        username = request.data.get('username')
        password = request.data.get('password')
        otp_code = request.data.get('otp_code', None)  # OTP input from user

        user = authenticate(username=username, password=password)
        if user is not None:
            # If TOTP is enabled, verify the OTP before allowing login
            if user.totp_secret:
                if not otp_code or not user.verify_totp(otp_code, valid_window=1):
                    return Response({'error': 'Invalid OTP'}, status=status.HTTP_401_UNAUTHORIZED)

            # Check if the user is a locksmith
            locksmith = None
            try:
                locksmith = Locksmith.objects.get(user=user)
                
                refresh = RefreshToken.for_user(user)
                # If the locksmith exists, check verification and approval status
                if not locksmith.is_verified:
                    return Response({
                        'message': 'Login successful',
                        'error': 'Your account is pending verification',
                        'user_id': user.id,
                        'username': user.username,
                        'role': user.role,
                        'is_locksmith': True,
                        'is_verified': False,
                        'is_approved': locksmith.is_approved,
                        'access': str(refresh.access_token),
                        'refresh': str(refresh)
                    }, status=status.HTTP_200_OK)

                if not locksmith.is_approved:
                    return Response({
                        'message': 'Login successful',
                        'error': 'Your account has been rejected',
                        'user_id': user.id,
                        'username': user.username,
                        'role': user.role,
                        'is_locksmith': True,
                        'is_verified': locksmith.is_verified,
                        'is_approved': False,
                        'access': str(refresh.access_token),
                        'refresh': str(refresh)
                    }, status=status.HTTP_200_OK)

            except Locksmith.DoesNotExist:
                pass  # User is not a locksmith

            # Generate authentication tokens
            refresh = RefreshToken.for_user(user)

            return Response({
                'message': 'Login successful',
                'user_id': user.id,
                'username': user.username,
                'role': user.role,
                'is_locksmith': True if locksmith else False,
                'is_verified': locksmith.is_verified if locksmith else None,
                'is_approved': locksmith.is_approved if locksmith else None,
                'access': str(refresh.access_token),
                'refresh': str(refresh)
            }, status=status.HTTP_200_OK)

        return Response({'error': 'Invalid credentials'}, status=status.HTTP_401_UNAUTHORIZED)


# Custom Permissions
class IsAdmin(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.role == 'admin'  # Adjust role check as per your user model

class IsLocksmith(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.role == 'locksmith'  # Adjust role check for locksmiths

class IsCustomer(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.role == 'customer'  # Adjust role check for customers
    
    
class IsAdminOrCustomer(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.role in ['admin', 'customer']

# Admin Views
class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsAdmin]  # Only Admin can manage users
    
    
    
class CustomersViewSet(viewsets.ModelViewSet):
    queryset = User.objects.filter(role='customer')
    serializer_class = UserSerializer
    permission_classes = [IsAdmin] 
    
class AllLocksmiths(viewsets.ReadOnlyModelViewSet):  # Use ReadOnlyModelViewSet if only listing
    queryset = User.objects.filter(role='locksmith')
    serializer_class = UserSerializer
    permission_classes = [IsAdmin]
    

class CarKeyDetailsViewSet(viewsets.ModelViewSet):
    queryset = CarKeyDetails.objects.all()
    serializer_class = CarKeyDetailsSerializer
    permission_classes = [IsAdmin]  # Only Admin can manage car key details

# class ServiceViewSet(viewsets.ModelViewSet):
#     queryset = LocksmithService.objects.all()
#     serializer_class = LocksmithServiceSerializer
#     # permission_classes=[IsAdminOrCustomer]

#     @action(detail=False, methods=['get'], permission_classes=[IsAdmin])
#     def platform_settings(self, request):
#         # Returns platform settings like commission percentage
#         platform_settings = AdminSettings.objects.first()
#         return Response({'commission_percentage': platform_settings.commission_percentage, 'platform_status': platform_settings.platform_status})



class AdminLocksmithServiceApprovalViewSet(viewsets.ViewSet):
    permission_classes = [IsAdminUser]
    
    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        service = get_object_or_404(LocksmithServices, pk=pk)
        service.approved = True
        service.save()
        return Response({"status": "Service approved"})

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        service = get_object_or_404(LocksmithServices, pk=pk)
        service.delete()
        return Response({"status": "Service rejected"})

class AdminLocksmithServiceViewSet(viewsets.ModelViewSet):
    """
    Admin can manage services that locksmiths can choose from.
    """
    queryset = AdminService.objects.all()
    serializer_class = AdminServiceSerializer
    permission_classes = [permissions.IsAdminUser]

    @action(detail=False, methods=['get'])
    def list_approved_services(self, request):
        """Get all services that are approved by the admin"""
        approved_services = LocksmithServices.objects.filter(approved=True)
        serializer = LocksmithServiceSerializer(approved_services, many=True)
        return Response(serializer.data)
    
    
    @action(detail=False, methods=['get'],permission_classes=[IsCustomer])
    def services_to_customer(self, request):
        """Get all approved services, optionally filtered by service type."""
        service_type = request.query_params.get('service_type', None)  # Get service type from request

        approved_services = LocksmithServices.objects.filter(approved=True)

        # Apply filtering if service_type is provided
        if service_type:
            approved_services = approved_services.filter(service_type=service_type)

        serializer = LocksmithServiceSerializer(approved_services, many=True)
        return Response(serializer.data)
    
    
    @action(detail=False, methods=['get'], permission_classes=[permissions.IsAuthenticated])
    def available_services(self, request):
        """
        Get all services added by the admin so the logged-in locksmith can choose.
        """
        services = AdminService.objects.all()
        serializer = AdminServiceSerializer(services, many=True)
        return Response(serializer.data)

    
    @action(detail=False, methods=['get'], permission_classes=[permissions.IsAdminUser])
    def all_locksmith_services(self, request):
        """
        Admin can view all services added by locksmiths (both approved and pending).
        """
        services = LocksmithServices.objects.all()
        serializer = LocksmithServiceSerializer(services, many=True)
        return Response(serializer.data)
    
    
    
    def destroy(self, request, pk=None):
        """Delete an admin service"""
        service = get_object_or_404(AdminService, pk=pk)
        service.delete()
        return Response({"status": "Service deleted successfully"}, status=status.HTTP_204_NO_CONTENT)
    
    
    
class ServiceViewSet(viewsets.ModelViewSet):
    serializer_class = LocksmithServiceSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Return only services belonging to the logged-in locksmith."""
        user = self.request.user
        try:
            locksmith = user.locksmith  # Ensure user is linked to a Locksmith
            return LocksmithServices.objects.filter(locksmith=locksmith)
        except AttributeError:
            return LocksmithServices.objects.none()  # Return empty if not a locksmith

    def perform_create(self, serializer):
        """Automatically assign the logged-in locksmith and calculate total price."""
        user = self.request.user

        try:
            locksmith = user.locksmith  # Ensure the user is linked to a Locksmith
            
            # Save service with locksmith and approved=False
            service = serializer.save(locksmith=locksmith, approved=False)

            # Calculate total price
            service.total_price = service.custom_price + service.admin_service.base_price
            service.save()

        except AttributeError:
            raise serializers.ValidationError({"error": "User is not associated with a locksmith account."})



class TransactionViewSet(viewsets.ModelViewSet):
    queryset = Transaction.objects.all()
    serializer_class = TransactionSerializer
    permission_classes = [IsAdmin]  # Only Admin can manage transactions

# Locksmith Views
class LocksmithDashboardViewSet(viewsets.GenericViewSet):
    permission_classes = [IsLocksmith]

    @action(detail=False, methods=['get'])
    def my_services(self, request):
        locksmith = Locksmith.objects.get(user=request.user)
        services = locksmith.services_offered.all()
        return Response(ServiceSerializer(services, many=True).data)

    @action(detail=False, methods=['get'])
    def my_transactions(self, request):
        locksmith = Locksmith.objects.get(user=request.user)
        transactions = Transaction.objects.filter(locksmith=locksmith)
        return Response(TransactionSerializer(transactions, many=True).data)

    @action(detail=False, methods=['put'])
    def update_service_prices(self, request):
        locksmith = Locksmith.objects.get(user=request.user)
        # Logic for updating prices
        return Response({'status': 'prices updated'})

class ServiceRequestViewSet(viewsets.ModelViewSet):
    queryset = ServiceRequest.objects.all()
    serializer_class = ServiceRequestSerializer
    permission_classes = [IsLocksmith]  # Locksmiths can manage service requests

    @action(detail=True, methods=['put'], permission_classes=[IsLocksmith])
    def accept_request(self, request, pk=None):
        service_request = self.get_object()
        service_request.status = 'ACCEPTED'
        service_request.save()
        return Response({'status': 'request accepted'})

    @action(detail=True, methods=['put'], permission_classes=[IsLocksmith])
    def reject_request(self, request, pk=None):
        service_request = self.get_object()
        service_request.status = 'REJECTED'
        service_request.save()
        return Response({'status': 'request rejected'})
    
class AdminSettingsViewSet(viewsets.ModelViewSet):
    queryset = AdminSettings.objects.all()
    serializer_class = AdminSettingsSerializer    
    
    
    


class AdmincomissionViewSet(viewsets.ModelViewSet):
    """
    ViewSet for updating or creating the admin percentage settings.
    Only accessible by Admins.
    """
    queryset = AdminSettings.objects.all()
    serializer_class = AdminSettingsSerializer
    permission_classes = [IsAuthenticated, IsAdmin]

    def update(self, request, *args, **kwargs):
        """
        Update the existing admin percentage or create a new one if none exists.
        Ensures a single row is maintained in the database.
        """
        admin_settings = AdminSettings.objects.first()  # Fetch the first record if exists

        if not admin_settings:
            # Create only if no record exists
            admin_settings = AdminSettings.objects.create(admin_percentage=request.data.get("admin_percentage", 0))
            message = "Admin percentage created successfully."
        else:
            # Update existing record
            admin_percentage = request.data.get("admin_percentage")
            if admin_percentage is not None:
                admin_settings.admin_percentage = admin_percentage
                admin_settings.save()
                message = "Admin percentage updated successfully."
            else:
                return Response({"error": "Admin percentage is required."}, status=status.HTTP_400_BAD_REQUEST)

        return Response({
            "message": message,
            "admin_percentage": admin_settings.admin_percentage
        }, status=status.HTTP_200_OK)




# class LocksmithServiceUpdateViewSet(viewsets.ModelViewSet):
#     """
#     ViewSet for updating locksmith services and pricing with admin commission.
#     Only accessible by Locksmiths.
#     """
#     queryset = LocksmithService.objects.all()
#     serializer_class = LocksmithServiceSerializer
#     permission_classes = [IsAuthenticated, IsLocksmith]

#     def update(self, request, *args, **kwargs):
#         """
#         Update locksmith service price with admin commission (Fixed Amount Model).
#         """
#         user = request.user
#         try:
#             locksmith = user.locksmith  # Ensure locksmith profile exists
#         except Locksmith.DoesNotExist:
#             return Response({"error": "Locksmith profile not found."}, status=status.HTTP_404_NOT_FOUND)

#         # Get the admin fixed commission amount
#         admin_settings = AdminSettings.objects.first()
#         if not admin_settings:
#             return Response({"error": "Admin settings not found."}, status=status.HTTP_404_NOT_FOUND)

#         commission_amount = admin_settings.commission_amount  # Fixed amount

#         services = request.data.get("services", [])

#         for service_data in services:
#             service_id = service_data.get("id")
#             base_price = service_data.get("price")

#             try:
#                 service = Service.objects.get(id=service_id, locksmith=locksmith)
#                 final_price = base_price + commission_amount  # Fixed amount addition

#                 service.price = final_price
#                 service.save()

#             except Service.DoesNotExist:
#                 return Response({"error": f"Service ID {service_id} not found."}, status=status.HTTP_404_NOT_FOUND)

#         return Response({
#             "message": "Services updated successfully with fixed admin commission.",
#             "commission_amount": commission_amount
#         }, status=status.HTTP_200_OK)



class ServiceBidViewSet(viewsets.ModelViewSet):
    queryset = ServiceBid.objects.all()
    serializer_class = ServiceBidSerializer
    permission_classes = [IsCustomer]  # Customers can place bids

    @action(detail=True, methods=['post'], permission_classes=[IsCustomer])
    def place_bid(self, request, pk=None):
        service_request = self.get_object()
        bid_amount = request.data.get('bid_amount')
        # Add logic for bid creation, and validation
        return Response({'status': 'bid placed'})

# Customer Views
class CustomerDashboardViewSet(viewsets.GenericViewSet):
    permission_classes = [IsCustomer]

    @action(detail=False, methods=['get'])
    def available_locksmiths(self, request):
        locksmiths = Locksmith.objects.filter(is_approved=True)
        return Response(LocksmithSerializer(locksmiths, many=True).data)

    @action(detail=False, methods=['get'])
    def my_bids(self, request):
        customer = User.objects.get(username=request.user.username)
        bids = ServiceBid.objects.filter(customer=customer)
        return Response(ServiceBidSerializer(bids, many=True).data)

    @action(detail=False, methods=['post'])
    def place_service_request(self, request):
        # Logic for creating service requests
        return Response({'status': 'service request placed'})






# class LocksmithServiceViewSet(viewsets.ModelViewSet):
#     queryset = LocksmithService.objects.all()
#     serializer_class = LocksmithServiceSerializer
#     permission_classes = [IsAuthenticated]

#     def create(self, request, *args, **kwargs):
#         """
#         Create a new locksmith service with admin commission included.
#         """
#         # Get the authenticated locksmith
#         user = request.user
#         try:
#             locksmith = Locksmith.objects.get(user=user)
#         except Locksmith.DoesNotExist:
#             return Response({"error": "Locksmith profile not found."}, status=status.HTTP_404_NOT_FOUND)

#         # Ensure the locksmith is approved before allowing service creation
#         if not locksmith.is_approved:
#             return Response({"error": "Locksmith is not approved."}, status=status.HTTP_403_FORBIDDEN)

#         # Extract the necessary data from the request
#         service_type = request.data.get("service_type")
#         base_price = request.data.get("price")
#         details = request.data.get("details", "")

#         # Validate price input
#         try:
#             base_price = float(base_price)
#         except (TypeError, ValueError):
#             return Response({"error": "Invalid price format."}, status=status.HTTP_400_BAD_REQUEST)

#         # Fetch admin commission amount and ensure it's a float
#         admin_settings = AdminSettings.objects.first()
#         commission_amount = admin_settings.commission_amount if admin_settings else 0.00
#         commission_amount = float(commission_amount)  # Make sure it's a float for calculation

#         # DEBUG: Print commission value and base price for clarity
#         print(f"Base Price: {base_price}, Commission Amount: {commission_amount}")

#         # Calculate the total price: base price + commission
#         total_price = base_price + commission_amount  # Ensure commission is added only once
#         print(f"Total Price (Base Price + Commission): {total_price}")

#         # Check if the locksmith already has a service entry for this service type
#         service = LocksmithService.objects.filter(locksmith=locksmith, service_type=service_type).first()

#         if service:
#             # If service exists, update it
#             service.price = total_price  # Only update the price field (don't add commission again)
#             service.details = details
#             service.save()
#             return Response({
#                 "message": "Service updated successfully with admin commission.",
#                 "service_id": service.id,
#                 "locksmith": locksmith.user.username,
#                 "service_type": service.service_type,
#                 "base_price": base_price,
#                 "admin_commission": commission_amount,
#                 "total_price": total_price
#             }, status=status.HTTP_200_OK)
#         else:
#             # If no existing service, create a new one
#             service = LocksmithService.objects.create(
#                 locksmith=locksmith,
#                 service_type=service_type,
#                 price=total_price,  # Store total price (base price + commission)
#                 details=details
#             )
#             return Response({
#                 "message": "Service created successfully with admin commission.",
#                 "service_id": service.id,
#                 "locksmith": locksmith.user.username,
#                 "service_type": service.service_type,
#                 "base_price": base_price,
#                 "admin_commission": commission_amount,
#                 "total_price": total_price
#             }, status=status.HTTP_201_CREATED)
            
            
            
            
            
            
            
            
            
            
class CustomerServiceRequestViewSet(viewsets.ModelViewSet):
    queryset = CustomerServiceRequest.objects.all()
    serializer_class = CustomerServiceRequestSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """Filter requests based on user role"""
        user = self.request.user
        queryset = CustomerServiceRequest.objects.all()

        # 🔹 Customers see only their requests
        if user.role == 'customer':
            queryset = queryset.filter(customer__user=user)

        # 🔹 Locksmiths see only assigned requests
        elif user.role == 'locksmith':
            queryset = queryset.filter(locksmith__user=user)

        # 🔹 Distance-based filtering (for customers)
        user_lat = self.request.query_params.get('latitude')
        user_lon = self.request.query_params.get('longitude')

        if user_lat and user_lon:
            user_location = Point(float(user_lon), float(user_lat), srid=4326)
            queryset = queryset.annotate(distance=Distance('locksmith__location', user_location)).order_by('distance')

        return queryset

    def perform_create(self, serializer):
        """Assign customer and trigger WebSocket update"""
        customer = get_object_or_404(Customer, user=self.request.user)
        service_request = serializer.save(customer=customer)

        # 🔹 Notify WebSocket clients
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            "service_requests",
            {"type": "service_request_update", "data": {"message": "New service request created"}}
        )

    def partial_update(self, request, *args, **kwargs):
        """Allow only locksmiths to update status and trigger WebSocket update"""
        service_request = self.get_object()

        if service_request.locksmith.user != request.user:
            return Response({"error": "Only the assigned locksmith can update this request."}, status=403)

        new_status = request.data.get('status')
        if new_status in ['accepted', 'rejected', 'completed']:
            service_request.status = new_status
            service_request.save()

            # 🔹 Notify WebSocket clients
            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.group_send)(
                "service_requests",
                {"type": "service_request_update", "data": {"message": f"Request {service_request.id} updated to {new_status}"}}
            )

            return Response({"message": f"Service request updated to {new_status}."})
        
        return Response({"error": "Invalid status update."}, status=400)
    
    
    
    
    
    
    
# class BookingViewSet(viewsets.ModelViewSet):
#     queryset = Booking.objects.all()
#     serializer_class = BookingSerializer
#     permission_classes = [permissions.IsAuthenticated]

#     def get_queryset(self):
#         """Filter bookings so locksmiths see only their own bookings"""
#         user = self.request.user
#         if hasattr(user, 'locksmith'):  # Ensure the user is a locksmith
#             return Booking.objects.filter(locksmith_service__locksmith=user.locksmith)
#         return Booking.objects.filter(customer=user)  # Customers see their bookings

#     def perform_create(self, serializer):
#         """Customers book a locksmith service"""
#         serializer.save(customer=self.request.user)

#     @action(detail=True, methods=['post'])
#     def complete(self, request, pk=None):
#         """Locksmith marks booking as completed"""
#         booking = self.get_object()
#         if booking.locksmith_service.locksmith.user != request.user:
#             return Response({'error': 'Permission denied'}, status=403)
#         booking.complete()
#         return Response({'status': 'Booking completed'})

#     @action(detail=True, methods=['post'])
#     def cancel(self, request, pk=None):
#         """Customer cancels the booking"""
#         booking = self.get_object()
#         if booking.customer != request.user:
#             return Response({'error': 'Permission denied'}, status=403)
#         booking.cancel()
#         return Response({'status': 'Booking canceled'})
    
    
    
    
    
import stripe
from django.conf import settings
from rest_framework.response import Response
from rest_framework.decorators import api_view
from .models import Locksmith    
    
stripe.api_key = settings.STRIPE_SECRET_KEY  # Use your Stripe Secret Key

class LocksmithViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing Locksmiths:
    - Admin approval/rejection
    - Stripe Account creation & onboarding
    - Checking onboarding status
    """
    queryset = Locksmith.objects.all()
    serializer_class = LocksmithSerializer
    permission_classes = [IsAdminUser]  # Only Admin can manage locksmiths

    # ✅ Verify Locksmith (Admin Only)
    @action(detail=True, methods=['put'], permission_classes=[IsAdminUser])
    def verify_locksmith(self, request, pk=None):
        locksmith = self.get_object()
        locksmith.is_verified = True
        locksmith.is_approved = True  # Approve upon verification
        locksmith.save()
        return Response({'status': 'Locksmith verified', 'locksmith_data': LocksmithSerializer(locksmith).data})

    # ✅ Reject Locksmith (Admin Only)
    @action(detail=True, methods=['put'], permission_classes=[IsAdminUser])
    def reject_locksmith(self, request, pk=None):
        locksmith = self.get_object()
        locksmith.is_verified = False
        locksmith.is_approved = False
        locksmith.save()
        return Response({'status': 'Locksmith rejected', 'locksmith_data': LocksmithSerializer(locksmith).data})

    # ✅ View Locksmith Details (Admin Only)
    @action(detail=True, methods=['get'], permission_classes=[IsAdminUser])
    def verify_locksmith_details(self, request, pk=None):
        locksmith = self.get_object()
        return Response(LocksmithSerializer(locksmith).data)

    # ✅ Create Stripe Express Account for Locksmith
    @action(detail=True, methods=['post'])
    def create_stripe_account(self, request, pk=None):
        locksmith = self.get_object()

        if locksmith.stripe_account_id:
            return Response({"message": "Stripe account already exists!", "stripe_account_id": locksmith.stripe_account_id})

        # Create a Stripe Express account
        stripe_account = stripe.Account.create(
            type="express",
            country="US",  # Change based on your country
            email=locksmith.user.email,
            capabilities={"card_payments": {"requested": True}, "transfers": {"requested": True}},
        )

        # Save Stripe Account ID
        locksmith.stripe_account_id = stripe_account.id
        locksmith.save()

        return Response({"message": "Stripe account created!", "stripe_account_id": stripe_account.id})

    # ✅ Generate Stripe Onboarding Link & Send Email
    @action(detail=True, methods=['get'])
    def generate_stripe_onboarding_link(self, request, pk=None):
        locksmith = self.get_object()

        if not locksmith.stripe_account_id:
            return Response({"error": "Locksmith does not have a Stripe account."}, status=400)

        account_link = stripe.AccountLink.create(
            account=locksmith.stripe_account_id,
            refresh_url="http://localhost:8000/reauth",
            return_url="http://localhost:8000/dashboard",
            type="account_onboarding",
        )

        # Send onboarding link via email
        send_mail(
            "Complete Your Stripe Verification",
            f"Hello {locksmith.user.username},\n\nPlease complete your Stripe account setup by clicking the link below:\n\n{account_link.url}\n\nThanks!",
            "your_email@example.com",  # Replace with your email
            [locksmith.user.email],
            fail_silently=False,
        )

        return Response({"message": "Onboarding link sent to locksmith's email!", "onboarding_url": account_link.url})

    # ✅ Check Stripe Onboarding Status
    @action(detail=True, methods=['get'])
    def check_onboarding_status(self, request, pk=None):
        locksmith = self.get_object()

        if not locksmith.stripe_account_id:
            return Response({"error": "Locksmith does not have a Stripe account."}, status=400)

        stripe_account = stripe.Account.retrieve(locksmith.stripe_account_id)

        return Response({
            "email": stripe_account.email,
            "payouts_enabled": stripe_account.payouts_enabled,
            "charges_enabled": stripe_account.charges_enabled,
            "requirements": stripe_account.requirements,
        })
        
        
        
        
class BookingViewSet(viewsets.ModelViewSet):
    """
    ViewSet for handling bookings, payments, and refunds.
    """
    queryset = Booking.objects.all()
    serializer_class = BookingSerializer

    @action(detail=True, methods=['post'])
    def process_payment(self, request, pk=None):
        """
        ✅ Process customer payment, deduct commission, and send the remaining amount to the locksmith.
        """
        booking = self.get_object()
        locksmith = booking.locksmith_service.locksmith

        if not locksmith.stripe_account_id:
            return Response({"error": "Locksmith does not have a Stripe account."}, status=400)

        # Calculate commission (10%)
        commission_percentage = 10 / 100
        commission_amount = booking.price * commission_percentage
        payout_amount = booking.price - commission_amount

        # Create PaymentIntent
        payment_intent = stripe.PaymentIntent.create(
            amount=int(booking.price * 100),  # Convert to cents
            currency="usd",
            application_fee_amount=int(commission_amount * 100),  # Platform's commission
            transfer_data={"destination": locksmith.stripe_account_id},  # Send remaining amount to locksmith
        )

        # Store PaymentIntent ID
        booking.payment_intent_id = payment_intent.id
        booking.payment_status = "paid"
        booking.save()

        return Response({"client_secret": payment_intent.client_secret, "payment_intent_id": payment_intent.id})

    @action(detail=True, methods=['post'])
    def process_refund(self, request, pk=None):
        """
        ✅ Process a refund for a booking.
        """
        booking = self.get_object()

        if not booking.payment_intent_id:
            return Response({"error": "PaymentIntent ID is missing."}, status=400)

        # Process refund
        refund = stripe.Refund.create(payment_intent=booking.payment_intent_id)

        # Update booking status
        booking.payment_status = "refunded"
        booking.save()

        return Response({"message": "Refund successful", "refund_id": refund.id})